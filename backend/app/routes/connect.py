"""Consent surface for "CaseRaft for Claude" (the MCP connector).

The MCP service (mcp.caseraft.com) is the OAuth 2.1 authorization server
Claude talks to, but IT does not own user sessions, Clio login, or the
subscription gate; this app does. So the MCP service's /authorize endpoint
302s the user's browser here with the original OAuth params, and this page:

  1. Requires a signed-in CaseRaft session (bouncing through the existing
     Clio OAuth login if needed).
  2. Enforces the subscription gate (is_paid covers admins + whitelist).
  3. Shows a consent page listing what Claude will be able to do.
  4. On approve, mints a single-use authorization code into mcp_auth_codes
     (SHA-256 hash only) and 302s back to the validated redirect_uri with
     code + state. The MCP service verifies PKCE at its /token endpoint.

Redirect URIs are validated against the client's DCR registration with the
same policy as the MCP service: exact match, or port-agnostic loopback
match for Claude Code (RFC 8252 style).
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db, limiter
from app.models.mcp import MCPAuthCode, MCPClient, MCPToken
from app.models.user import User
from app.services.audit import record_audit

connect_bp = Blueprint("connect", __name__)

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"
LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}
AUTH_CODE_TTL = timedelta(minutes=10)

# What the connector can do today; shown verbatim on the consent page.
TOOL_DESCRIPTIONS = [
    ("Verify your connection", "Look up your Clio name, email, and firm."),
    ("Matters", "List and look up your matters, with billing summaries."),
    ("Contacts", "Search contacts and view contact details."),
    ("Firm productivity", "Hours, billable split, and utilization by person."),
    ("Outstanding revenue", "Collected vs outstanding AR by practice area."),
    ("Trust balances", "Trust account balances and per-client deficits."),
    ("Daily digest", "Tasks due, calendar, and unpaid bills for the day."),
]
UPCOMING_NOTE = (
    "All tools are read-only. Claude can look things up on your behalf "
    "but can never change anything in Clio."
)


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="mcp-consent"
    )


def _sha256_hex(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _is_loopback(uri):
    parsed = urlparse(str(uri))
    return parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS


def _loopback_match(candidate, registered):
    if not (_is_loopback(candidate) and _is_loopback(registered)):
        return False
    return (urlparse(candidate).path or "/") == (urlparse(registered).path or "/")


def _redirect_uri_valid(candidate, registered_uris):
    for registered in registered_uris or []:
        if candidate == registered:
            return True
        if _loopback_match(candidate, registered):
            return True
    return False


_PAGE_SHELL = """<!doctype html><html><head>
<meta charset='utf-8'>
<title>{{ title }} · Case Raft</title>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:#f7f7f8;color:#1a1a1a;margin:0;padding:0;
display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{max-width:520px;margin:24px;padding:40px 36px;background:#fff;
border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.06)}
h1{font-size:22px;margin:0 0 12px}
p{line-height:1.55;color:#444;margin:0 0 12px}
ul{margin:0 0 16px;padding-left:20px}
li{line-height:1.55;color:#444;margin-bottom:6px}
a{color:#2b6cb0;text-decoration:none}a:hover{text-decoration:underline}
.muted{color:#777;font-size:13px;margin-top:20px}
.actions{display:flex;gap:12px;margin-top:24px}
button{font-size:15px;padding:10px 22px;border-radius:8px;border:0;cursor:pointer}
.approve{background:#2b6cb0;color:#fff}
.deny{background:#eee;color:#333}
</style></head><body><div class='card'>{{ body }}</div></body></html>"""


def _render_page(title, body_html, status=200):
    html = render_template_string(
        _PAGE_SHELL.replace("{{ body }}", body_html), title=title
    )
    return Response(html, status=status, mimetype="text/html")


def _error_page(message, status=400):
    return _render_page(
        "Connection error",
        "<h1>Can't connect Claude</h1>"
        f"<p>{message}</p>"
        "<p>Please start the connection again from Claude. If this keeps "
        "happening, email <a href='mailto:support@caseraft.com'>"
        "support@caseraft.com</a>.</p>",
        status=status,
    )


def _collect_params():
    """OAuth params relayed by the MCP service's /authorize endpoint."""
    return {
        "client_id": request.args.get("client_id", ""),
        "redirect_uri": request.args.get("redirect_uri", ""),
        "state": request.args.get("state", ""),
        "code_challenge": request.args.get("code_challenge", ""),
        "code_challenge_method": request.args.get("code_challenge_method", "S256"),
        "scope": request.args.get("scope", ""),
        "response_type": request.args.get("response_type", "code"),
    }


@connect_bp.route("/authorize", methods=["GET"])
@limiter.limit("30 per minute")
def authorize():
    params = _collect_params()

    # A signed-out user who just came back from Clio login arrives with no
    # query params; restore the stashed authorization request.
    if not params["client_id"] and "mcp_authorize_params" in session:
        params = session.pop("mcp_authorize_params")

    # ---- Validate the OAuth request BEFORE anything user-facing ----
    if not params["client_id"] or not params["redirect_uri"]:
        return _error_page("The connection request is missing required "
                           "parameters (client_id / redirect_uri).")
    if params["response_type"] != "code":
        return _error_page("Unsupported response_type; only 'code' is supported.")
    if not params["code_challenge"] or params["code_challenge_method"] != "S256":
        return _error_page("A PKCE S256 code challenge is required.")

    client = MCPClient.query.filter_by(client_id=params["client_id"]).first()
    if client is None:
        return _error_page("Unknown client. Claude should register first.")
    if not _redirect_uri_valid(params["redirect_uri"], client.redirect_uris):
        # NEVER redirect to an unvalidated URI
        return _error_page("The redirect URI is not registered for this client.")

    # ---- Session gate: bounce through the existing Clio login ----
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    if user is None:
        session["mcp_authorize_params"] = params
        return redirect("/auth/login")

    # ---- Subscription gate (is_paid covers admin + whitelist) ----
    if not user.is_paid:
        record_audit("mcp_consent_refused_unpaid", user=user,
                     detail=f"client_id={params['client_id']}")
        return _render_page(
            "Upgrade required",
            "<h1>CaseRaft for Claude needs an active plan</h1>"
            "<p>Connecting Claude to your Clio data is included with every "
            "paid CaseRaft plan.</p>"
            "<p><a href='/billing'>Choose a plan</a> and then start the "
            "connection again from Claude.</p>"
            "<p class='muted'>Signed in as " + (user.email or "") + "</p>",
            status=403,
        )

    # ---- Render consent ----
    grant = _serializer().dumps({"params": params, "user_id": user.id})
    tools_html = "".join(
        f"<li><strong>{name}</strong>: {desc}</li>"
        for name, desc in TOOL_DESCRIPTIONS
    )
    body = (
        "<h1>Claude wants to access your Clio data through CaseRaft</h1>"
        f"<p>Approving lets <strong>{(client.client_name or 'Claude')}</strong> "
        "use these read-only tools on your behalf:</p>"
        f"<ul>{tools_html}</ul>"
        f"<p class='muted'>{UPCOMING_NOTE}</p>"
        "<p>Every access is audit-logged. You can revoke this connection at "
        "any time from your CaseRaft settings.</p>"
        "<form method='post'>"
        f"<input type='hidden' name='grant' value='{grant}'>"
        "<div class='actions'>"
        "<button class='approve' type='submit' name='action' value='approve'>"
        "Approve</button>"
        "<button class='deny' type='submit' name='action' value='deny'>"
        "Deny</button>"
        "</div></form>"
        f"<p class='muted'>Signed in as {user.email}</p>"
    )
    return _render_page("Connect Claude", body)


@connect_bp.route("/authorize", methods=["POST"])
@limiter.limit("30 per minute")
def authorize_decision():
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    if user is None:
        return _error_page("Your session expired. Start again from Claude.", 401)

    try:
        payload = _serializer().loads(request.form.get("grant", ""), max_age=600)
    except (BadSignature, SignatureExpired):
        return _error_page("This consent form expired. Start again from Claude.")

    if payload.get("user_id") != user.id:
        return _error_page("This consent form belongs to a different session.")

    params = payload["params"]

    # Re-validate against the registration (client could have been deleted)
    client = MCPClient.query.filter_by(client_id=params["client_id"]).first()
    if client is None or not _redirect_uri_valid(
        params["redirect_uri"], client.redirect_uris
    ):
        return _error_page("The client registration is no longer valid.")

    def _redirect_back(extra):
        query = dict(extra)
        if params.get("state"):
            query["state"] = params["state"]
        separator = "&" if urlparse(params["redirect_uri"]).query else "?"
        return redirect(f"{params['redirect_uri']}{separator}{urlencode(query)}")

    if request.form.get("action") != "approve":
        record_audit("mcp_consent_denied", user=user,
                     detail=f"client_id={params['client_id']}")
        return _redirect_back({"error": "access_denied"})

    # Subscription gate again (defense in depth; state may change mid-flow)
    if not user.is_paid:
        return _redirect_back({"error": "access_denied",
                               "error_description": "subscription required"})

    # ---- Mint the single-use authorization code (store hash only) ----
    code = "crc_" + secrets.token_urlsafe(43)  # > 256 bits of entropy
    db.session.add(
        MCPAuthCode(
            code_hash=_sha256_hex(code),
            user_id=user.id,
            client_id=params["client_id"],
            code_challenge=params["code_challenge"],
            scopes=params.get("scope") or None,
            redirect_uri=params["redirect_uri"],
            expires_at=datetime.utcnow() + AUTH_CODE_TTL,
            used=False,
        )
    )
    db.session.commit()
    record_audit("mcp_consent_granted", user=user,
                 detail=f"client_id={params['client_id']}")

    return _redirect_back({"code": code})


# ---------------------------------------------------------------------------
# Settings card endpoints (Phase 4.3). Session-authenticated JSON, consumed
# by the "Claude Connector" card in the React app. A token row counts as an
# active connection while `revoked` is false: access tokens expire, but the
# row (with its refresh token) lives until rotation replaces it or the user
# revokes here.
# ---------------------------------------------------------------------------


def _session_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


@connect_bp.route("/status", methods=["GET"])
def connection_status():
    """Connection status for the settings card.

    Returns: connected (any non-revoked mcp_tokens row for this user),
    last_used_at (most recent tool call across active rows, ISO 8601 UTC
    or null), client_count (distinct Claude clients connected).
    """
    user = _session_user()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401

    active = MCPToken.query.filter_by(user_id=user.id, revoked=False).all()
    last_used = max(
        (t.last_used_at for t in active if t.last_used_at is not None),
        default=None,
    )
    return jsonify({
        "connected": bool(active),
        "last_used_at": last_used.isoformat() + "Z" if last_used else None,
        "client_count": len({t.client_id for t in active}),
    })


@connect_bp.route("/revoke", methods=["POST"])
def revoke_connection():
    """Revoke the Claude connector: flip `revoked` on every active token row.

    The MCP service's bearer middleware rejects revoked tokens, so Claude
    gets a clean auth error on its next call and must reconnect through the
    consent flow to regain access.
    """
    user = _session_user()
    if user is None:
        return jsonify({"error": "Not authenticated"}), 401

    rows = MCPToken.query.filter_by(user_id=user.id, revoked=False).all()
    for row in rows:
        row.revoked = True
    db.session.commit()

    record_audit("mcp_connector_revoked", user=user,
                 detail=f"tokens_revoked={len(rows)}")
    return jsonify({"revoked": len(rows)})
