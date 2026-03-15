import os
from datetime import datetime, timedelta

import requests
from flask import Blueprint, current_app, redirect, request, session, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models.user import User
from app.services.clio_client import ClioAPIClient

auth_bp = Blueprint("auth", __name__)


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


@auth_bp.route("/login")
def login():
    """Redirect the user to Clio's OAuth authorization page."""
    # Use a signed state token instead of session (avoids cookie issues with proxies)
    s = _get_serializer()
    state = s.dumps("oauth-state")

    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": current_app.config["CLIO_CLIENT_ID"],
        "redirect_uri": current_app.config["CLIO_REDIRECT_URI"],
        "state": state,
    }
    query = urlencode(params)
    auth_url = f"{current_app.config['CLIO_AUTH_URL']}?{query}"
    return redirect(auth_url)


@auth_bp.route("/callback")
def callback():
    """Handle the OAuth callback from Clio."""
    # Validate signed state token (valid for 5 minutes)
    state = request.args.get("state")
    s = _get_serializer()
    try:
        s.loads(state, max_age=300)
    except (BadSignature, SignatureExpired):
        return jsonify({"error": "Invalid or expired state parameter"}), 400

    # Check for error (user declined)
    error = request.args.get("error")
    if error:
        return jsonify({"error": f"Authorization denied: {error}"}), 400

    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No authorization code received"}), 400

    # Exchange code for tokens
    token_resp = requests.post(
        current_app.config["CLIO_TOKEN_URL"],
        data={
            "client_id": current_app.config["CLIO_CLIENT_ID"],
            "client_secret": current_app.config["CLIO_CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": current_app.config["CLIO_REDIRECT_URI"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if token_resp.status_code != 200:
        return jsonify({"error": "Failed to exchange code for token", "details": token_resp.text}), 400

    token_data = token_resp.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])

    # Get user info from Clio Manage
    clio = ClioAPIClient(access_token, refresh_token, expires_at, user_id=None)
    user_info = clio.get_current_user()
    email = user_info["data"]["email"]

    # Upsert user
    user = User.query.filter_by(email=email).first()
    if user:
        user.clio_access_token = access_token
        user.clio_refresh_token = refresh_token
        user.token_expires_at = expires_at
        user.updated_at = datetime.utcnow()
    else:
        user = User(
            email=email,
            clio_access_token=access_token,
            clio_refresh_token=refresh_token,
            token_expires_at=expires_at,
        )
        db.session.add(user)

    db.session.commit()

    # Store user ID in session
    session["user_id"] = user.id

    # Redirect back to the same origin so the session cookie is on the right domain
    return redirect(f"{request.host_url}cases")


@auth_bp.route("/status")
def status():
    """Check if the user is logged in."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "plan_tier": user.effective_plan_tier,
            "subscription_status": user.subscription_status,
            "is_paid": user.is_paid,
        },
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the session."""
    session.clear()
    return jsonify({"message": "Logged out"})
