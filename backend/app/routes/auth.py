import os
import secrets
from datetime import datetime, timedelta

import requests
from flask import Blueprint, Response, current_app, redirect, request, session, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db, limiter
from app.models.user import User
from app.services.audit import record_audit
from app.services.clio_client import ClioAPIClient, HTTP_TIMEOUT

auth_bp = Blueprint("auth", __name__)


def _get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


@auth_bp.route("/login")
@limiter.limit("10 per minute")
def login():
    """Redirect the user to Clio's OAuth authorization page.

    Accepts an optional ?tier=solo|team|firm query parameter. The tier is
    carried through the signed OAuth state token so that after the callback
    creates the account we can drop the user straight into Stripe checkout
    for the plan they picked on the landing page — instead of stranding
    them on a page with no subscription.
    """
    client_id = current_app.config.get("CLIO_CLIENT_ID")
    redirect_uri = current_app.config.get("CLIO_REDIRECT_URI")

    # If Clio OAuth isn't configured, fail loudly with a clear message
    # instead of blindly redirecting the user to a broken Clio URL that
    # 404s. A missing or stale CLIO_CLIENT_ID / CLIO_REDIRECT_URI is the
    # root cause of the "click Connect → 404" report.
    if not client_id or not redirect_uri:
        current_app.logger.error(
            "Clio OAuth misconfigured: CLIO_CLIENT_ID set=%s CLIO_REDIRECT_URI set=%s",
            bool(client_id),
            bool(redirect_uri),
        )
        # User hits this via a top-level browser redirect, so return
        # an HTML page rather than raw JSON.
        html = (
            "<!doctype html><html><head>"
            "<meta charset='utf-8'>"
            "<title>Sign-in temporarily unavailable · Case Raft</title>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<style>"
            "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
            "background:#f7f7f8;color:#1a1a1a;margin:0;padding:0;"
            "display:flex;align-items:center;justify-content:center;min-height:100vh}"
            ".card{max-width:520px;margin:24px;padding:40px 36px;background:#fff;"
            "border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.06)}"
            "h1{font-size:22px;margin:0 0 12px}"
            "p{line-height:1.55;color:#444;margin:0 0 12px}"
            "a{color:#2b6cb0;text-decoration:none}a:hover{text-decoration:underline}"
            ".muted{color:#777;font-size:13px;margin-top:20px}"
            "</style></head><body>"
            "<div class='card'>"
            "<h1>Sign-in is temporarily unavailable</h1>"
            "<p>We're having trouble reaching our Clio integration right now. "
            "Nothing is wrong with your account — this is on our side.</p>"
            "<p>Please try again in a few minutes, or email "
            "<a href='mailto:support@caseraft.com'>support@caseraft.com</a> "
            "and we'll get you sorted.</p>"
            "<p><a href='/'>← Back to homepage</a></p>"
            "<p class='muted'>Error code: CLIO_OAUTH_NOT_CONFIGURED</p>"
            "</div></body></html>"
        )
        return Response(html, status=503, mimetype="text/html")

    # Capture the plan the user picked on the landing page (if any).
    tier = (request.args.get("tier") or "").lower()
    if tier not in ("solo", "team", "firm"):
        tier = None

    # Generate a per-user nonce, store in session, and embed in a signed
    # state token. The callback verifies the signature AND that the nonce
    # matches what's in the session — preventing login CSRF / state reuse.
    nonce = secrets.token_urlsafe(32)
    session["oauth_nonce"] = nonce

    s = _get_serializer()
    state_payload = {"nonce": nonce}
    if tier:
        state_payload["tier"] = tier
    state = s.dumps(state_payload)

    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
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

    # Tier the user picked on the landing page, if any.
    selected_tier = state_data.get("tier") if isinstance(state_data, dict) else None
    if selected_tier not in ("solo", "team", "firm"):
        selected_tier = None

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
    # Defend against a malformed Clio response (200 OK + partial JSON,
    # HTML during a Clio outage, future schema drift). Matches the same
    # guard the refresh path uses in clio_client.py — keeps a bad payload
    # from raising an opaque 500 instead of the proper 400 paths above.
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")
    if not access_token or not refresh_token or not isinstance(expires_in, (int, float)):
        current_app.logger.error(
            "Clio OAuth callback: malformed token response. Keys=%s",
            list(token_data.keys()) if isinstance(token_data, dict) else type(token_data).__name__,
        )
        return jsonify({"error": "Clio returned an invalid token response. Please try again."}), 400
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

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

    # Store user ID in session and mark it permanent so the
    # PERMANENT_SESSION_LIFETIME (7 days) takes effect.
    session.permanent = True
    session["user_id"] = user.id

    record_audit("login", user=user)

    # Redirect back to the same origin so the session cookie is on the right domain.
    # If the user came from the landing page and picked a plan, send them to
    # Billing with a start_checkout flag so the frontend auto-launches Stripe
    # checkout. Existing paid users always go straight to /cases.
    base = request.host_url.rstrip("/")
    if selected_tier and not user.is_paid:
        return redirect(f"{base}/billing?start_checkout={selected_tier}")
    return redirect(f"{base}/cases")


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
            # Frontend uses this flag instead of hardcoding an email. The
            # allowed set is intentionally kept in sync with the backend
            # check in reports.generate_firm_report.
            "can_view_trust_report": bool(user.email) and user.email.lower() in {"srhoades@trustice.us"},
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
    session.permanent = True
    session["user_id"] = user.id

    # In dev, redirect to the Vite frontend origin so the session cookie
    # stays on the right port and the SPA handles routing.
    frontend_url = request.args.get("next", "http://localhost:5173/cases")
    return redirect(frontend_url)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the session."""
    user_id = session.get("user_id")
    if user_id:
        record_audit("logout", user=User.query.get(user_id))
    session.clear()
    return jsonify({"message": "Logged out"})
