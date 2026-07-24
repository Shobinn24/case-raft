"""Tests for the /connect/authorize consent surface (CaseRaft for Claude)."""

import hashlib
import re
from urllib.parse import parse_qs, urlparse

import pytest


CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"

AUTH_PARAMS = {
    "response_type": "code",
    "client_id": "test-mcp-client",
    "redirect_uri": CLAUDE_CALLBACK,
    "state": "claude-state-123",
    "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    "code_challenge_method": "S256",
    "scope": "clio:read offline_access",
}


@pytest.fixture
def mcp_client(app):
    """A DCR registration row, as the MCP service's /register would create."""
    from app.extensions import db
    from app.models.mcp import MCPClient

    row = MCPClient(
        client_id="test-mcp-client",
        client_name="Claude",
        redirect_uris=[CLAUDE_CALLBACK],
    )
    db.session.add(row)
    db.session.commit()
    return row


def _sign_in(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id


def test_signed_out_user_bounces_to_clio_login(client, mcp_client):
    resp = client.get("/connect/authorize", query_string=AUTH_PARAMS)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/auth/login")
    # The authorization request is stashed for after the login round-trip
    with client.session_transaction() as sess:
        stashed = sess["mcp_authorize_params"]
    assert stashed["client_id"] == "test-mcp-client"
    assert stashed["state"] == "claude-state-123"


def test_unpaid_user_gets_friendly_refusal(client, make_user, mcp_client):
    user = make_user(email="freeuser@example.com", plan_tier="free",
                     subscription_status="free")
    _sign_in(client, user)
    resp = client.get("/connect/authorize", query_string=AUTH_PARAMS)
    assert resp.status_code == 403
    page = resp.get_data(as_text=True)
    assert "plan" in page.lower()
    assert "/billing" in page


def test_whitelisted_user_approve_mints_hashed_code(client, make_user,
                                                    mcp_client, app):
    from app.models.mcp import MCPAuthCode

    # trustice.us domain is whitelisted, so is_paid passes without Stripe
    user = make_user(email="srhoades@trustice.us", plan_tier="free",
                     subscription_status="free")
    _sign_in(client, user)

    consent = client.get("/connect/authorize", query_string=AUTH_PARAMS)
    assert consent.status_code == 200
    page = consent.get_data(as_text=True)
    assert "Claude" in page
    assert "Trust balances" in page
    assert "read-only" in page

    grant = re.search(r"name='grant' value='([^']+)'", page).group(1)
    resp = client.post(
        "/connect/authorize",
        data={"grant": grant, "action": "approve"},
    )
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert location.startswith(CLAUDE_CALLBACK)
    query = parse_qs(urlparse(location).query)
    assert query["state"] == ["claude-state-123"]
    code = query["code"][0]

    row = MCPAuthCode.query.one()
    assert row.user_id == user.id
    assert row.client_id == "test-mcp-client"
    assert row.code_challenge == AUTH_PARAMS["code_challenge"]
    assert row.redirect_uri == CLAUDE_CALLBACK
    assert row.used is False
    # Only the SHA-256 hash is stored, never the raw code
    assert row.code_hash == hashlib.sha256(code.encode()).hexdigest()
    assert code not in (row.code_hash, row.id)


def test_deny_redirects_with_access_denied(client, make_user, mcp_client):
    user = make_user(email="srhoades@trustice.us", plan_tier="free",
                     subscription_status="free")
    _sign_in(client, user)
    consent = client.get("/connect/authorize", query_string=AUTH_PARAMS)
    grant = re.search(
        r"name='grant' value='([^']+)'", consent.get_data(as_text=True)
    ).group(1)
    resp = client.post(
        "/connect/authorize",
        data={"grant": grant, "action": "deny"},
    )
    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.headers["Location"]).query)
    assert query["error"] == ["access_denied"]
    assert query["state"] == ["claude-state-123"]

    from app.models.mcp import MCPAuthCode
    assert MCPAuthCode.query.count() == 0


def test_unknown_client_is_rejected_without_redirect(client, make_user):
    user = make_user(email="srhoades@trustice.us")
    _sign_in(client, user)
    resp = client.get("/connect/authorize", query_string=AUTH_PARAMS)
    assert resp.status_code == 400
    assert "Unknown client" in resp.get_data(as_text=True)


def test_unregistered_redirect_uri_is_rejected(client, make_user, mcp_client):
    user = make_user(email="srhoades@trustice.us")
    _sign_in(client, user)
    params = dict(AUTH_PARAMS, redirect_uri="https://evil.example.com/cb")
    resp = client.get("/connect/authorize", query_string=params)
    assert resp.status_code == 400


def test_loopback_redirect_uri_matches_port_agnostically(client, make_user,
                                                         app):
    """Claude Code registers a loopback URI; any port must match."""
    from app.extensions import db
    from app.models.mcp import MCPClient

    db.session.add(MCPClient(
        client_id="claude-code-client",
        client_name="Claude Code",
        redirect_uris=["http://localhost:41321/callback"],
    ))
    db.session.commit()

    user = make_user(email="srhoades@trustice.us")
    _sign_in(client, user)
    params = dict(
        AUTH_PARAMS,
        client_id="claude-code-client",
        redirect_uri="http://127.0.0.1:60123/callback",
    )
    resp = client.get("/connect/authorize", query_string=params)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Settings card endpoints: GET /connect/status and POST /connect/revoke
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta  # noqa: E402


def _make_token(user, client_id="test-mcp-client", revoked=False,
                last_used_at=None, suffix="a"):
    """Insert an mcp_tokens row the way the MCP service's /token would."""
    from app.extensions import db
    from app.models.mcp import MCPToken

    row = MCPToken(
        token_hash=hashlib.sha256(
            f"tok-{user.id}-{client_id}-{suffix}".encode()
        ).hexdigest(),
        refresh_token_hash=hashlib.sha256(
            f"ref-{user.id}-{client_id}-{suffix}".encode()
        ).hexdigest(),
        user_id=user.id,
        client_id=client_id,
        scopes="clio:read offline_access",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        revoked=revoked,
        last_used_at=last_used_at,
    )
    db.session.add(row)
    db.session.commit()
    return row


def test_status_requires_login(client):
    resp = client.get("/connect/status")
    assert resp.status_code == 401


def test_status_with_no_tokens(client, make_user):
    user = make_user(email="paid@example.com")
    _sign_in(client, user)
    resp = client.get("/connect/status")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "connected": False,
        "last_used_at": None,
        "client_count": 0,
    }


def test_status_with_one_active_token(client, make_user):
    user = make_user(email="paid@example.com")
    used_at = datetime(2026, 7, 20, 14, 30, 0)
    _make_token(user, last_used_at=used_at)
    # A revoked row must not count toward connected/client_count
    _make_token(user, client_id="old-client", revoked=True, suffix="b")
    _sign_in(client, user)

    resp = client.get("/connect/status")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["connected"] is True
    assert body["client_count"] == 1
    assert body["last_used_at"] == "2026-07-20T14:30:00Z"


def test_status_only_shows_own_tokens(client, make_user):
    user = make_user(email="paid@example.com")
    other = make_user(email="other@example.com")
    _make_token(other)
    _sign_in(client, user)

    body = client.get("/connect/status").get_json()
    assert body["connected"] is False
    assert body["client_count"] == 0


def test_revoke_requires_login(client):
    resp = client.post("/connect/revoke")
    assert resp.status_code == 401


def test_revoke_flips_all_active_tokens(client, make_user):
    from app.models.mcp import MCPToken

    user = make_user(email="paid@example.com")
    other = make_user(email="other@example.com")
    _make_token(user, suffix="a")
    _make_token(user, client_id="second-client", suffix="b")
    untouched = _make_token(other, suffix="c")
    _sign_in(client, user)

    resp = client.post("/connect/revoke")
    assert resp.status_code == 200
    assert resp.get_json() == {"revoked": 2}

    assert all(
        row.revoked for row in MCPToken.query.filter_by(user_id=user.id)
    )
    # Another user's connection is untouched
    assert MCPToken.query.get(untouched.id).revoked is False

    # Status now reports disconnected
    body = client.get("/connect/status").get_json()
    assert body["connected"] is False

    # Revoking again is a harmless no-op
    resp = client.post("/connect/revoke")
    assert resp.get_json() == {"revoked": 0}
