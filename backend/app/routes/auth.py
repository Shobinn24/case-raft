import os
import secrets
from datetime import datetime, timedelta

import requests
from flask import Blueprint, current_app, redirect, request, session, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models.user import User
from app.services.clio_client import ClioAPIClient, HTTP_TIMEOUT

auth_bp = Blueprint("auth", __name__)


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


@auth_bp.route("/login")
def login():
    """Redirect the user to Clio's OAuth authorization page."""
    # Generate a per-user nonce, store in session, and embed in a signed
    # state token. The callback verifies the signature AND that the nonce
    # matches what's in the session — preventing login CSRF / state reuse.
    nonce = secrets.token_urlsafe(32)
    session["oauth_nonce"] = nonce

    s = _get_serializer()
    state = s.dumps({"nonce": nonce})

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
    # Validate signed state token (valid for 5 minutes) AND bind it to the
    # session nonce stored at /login time.
    state = request.args.get("state")
    s = _get_serializer()
    try:
        state_data = s.loads(state, max_age=300)
    except (BadSignature, SignatureExpired):
        return jsonify({"error": "Invalid or expired state parameter"}), 400

    expected_nonce = session.pop("oauth_nonce", None)
    received_nonce = state_data.get("nonce") if isinstance(state_data, dict) else None
    if not expected_nonce or not received_nonce or expected_nonce != received_nonce:
        return jsonify({"error": "State nonce mismatch"}), 400

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
        timeout=HTTP_TIMEOUT,
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
    user_tz = user_info["data"].get("time_zone")

    # Upsert user
    user = User.query.filter_by(email=email).first()
    if user:
        user.clio_access_token = access_token
        user.clio_refresh_token = refresh_token
        user.token_expires_at = expires_at
        user.timezone = user_tz
        user.updated_at = datetime.utcnow()
    else:
        user = User(
            email=email,
            clio_access_token=access_token,
            clio_refresh_token=refresh_token,
            token_expires_at=expires_at,
            timezone=user_tz,
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
            "is_admin": user.check_is_admin,
        },
    })


@auth_bp.route("/dev-login")
def dev_login():
    """Quick login for local development — bypasses Clio OAuth entirely.

    Hard-blocked in production via multiple guards (defense in depth):
    1. Flask debug must be on
    2. FLASK_ENV must be "development"
    3. If DEV_LOGIN_KEY is configured, ?key= must match

    Creates (or reuses) a dev user with dummy Clio tokens so that the
    mock-data layer in ClioAPIClient kicks in automatically.
    """
    # Hard block in production — multiple guards for defense in depth
    if not current_app.debug:
        return jsonify({"error": "Not found"}), 404
    if os.environ.get("FLASK_ENV") != "development":
        return jsonify({"error": "Not found"}), 404
    # Require shared secret if configured
    dev_key = os.environ.get("DEV_LOGIN_KEY")
    if dev_key and request.args.get("key") != dev_key:
        return jsonify({"error": "Not found"}), 404

    dev_email = "shobinn24@gmail.com"
    dummy_token = "dev-mock-token"
    expires = datetime.utcnow() + timedelta(days=365)

    user = User.query.filter_by(email=dev_email).first()
    if user:
        user.clio_access_token = dummy_token
        user.clio_refresh_token = dummy_token
        user.token_expires_at = expires
        user.updated_at = datetime.utcnow()
    else:
        user = User(
            email=dev_email,
            clio_access_token=dummy_token,
            clio_refresh_token=dummy_token,
            token_expires_at=expires,
            timezone="Eastern Time (US & Canada)",
        )
        db.session.add(user)

    db.session.commit()
    session["user_id"] = user.id

    # In dev, redirect to the Vite frontend origin so the session cookie
    # stays on the right port and the SPA handles routing.
    frontend_url = request.args.get("next", "http://localhost:5173/cases")
    return redirect(frontend_url)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the session."""
    session.clear()
    return jsonify({"message": "Logged out"})
