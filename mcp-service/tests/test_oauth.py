"""OAuth server tests: DCR, PKCE, code lifecycle, rotation, revocation,
subscription gating, and discovery metadata."""

from datetime import datetime, timedelta

from caseraft_mcp.config import settings
from caseraft_mcp.crypto import sha256_hex
from caseraft_mcp.db import MCPClient, MCPToken, session_scope

from .conftest import CLAUDE_CALLBACK, get_token_row, make_pkce_pair


# ---------------------------------------------------------------------------
# Dynamic Client Registration
# ---------------------------------------------------------------------------

def test_dcr_happy_path(client):
    resp = client.post(
        "/register",
        json={
            "client_name": "Claude",
            "redirect_uris": [CLAUDE_CALLBACK],
            "token_endpoint_auth_method": "none",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"]
    # Normalized to a public client: PKCE only, no secret stored or returned
    assert body.get("client_secret") is None
    assert body["token_endpoint_auth_method"] == "none"

    with session_scope() as session:
        row = (
            session.query(MCPClient)
            .filter_by(client_id=body["client_id"])
            .one()
        )
        assert row.client_name == "Claude"
        assert row.redirect_uris == [CLAUDE_CALLBACK]


def test_dcr_rejects_non_claude_non_loopback_redirect(client):
    resp = client.post(
        "/register",
        json={
            "client_name": "Evil",
            "redirect_uris": ["https://evil.example.com/callback"],
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_redirect_uri"


def test_dcr_accepts_loopback_redirects(client):
    resp = client.post(
        "/register",
        json={
            "client_name": "Claude Code",
            "redirect_uris": ["http://localhost:41321/callback",
                              "http://127.0.0.1:9999/callback"],
        },
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# /authorize relays the browser to the Flask consent page
# ---------------------------------------------------------------------------

def test_authorize_redirects_to_consent_url(client, register_client):
    registration = register_client()
    verifier, challenge = make_pkce_pair()
    resp = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registration["client_id"],
            "redirect_uri": CLAUDE_CALLBACK,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "abc123",
            "scope": "clio:read offline_access",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith(settings.consent_url)
    assert "code_challenge=" in location
    assert "state=abc123" in location
    assert "client_id=" + registration["client_id"] in location


def test_authorize_loopback_redirect_is_port_agnostic(client, register_client):
    """Registered with one loopback port, authorized with another."""
    registration = register_client(
        redirect_uris=["http://localhost:41321/callback"]
    )
    verifier, challenge = make_pkce_pair()
    resp = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": registration["client_id"],
            "redirect_uri": "http://127.0.0.1:55555/callback",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"].startswith(settings.consent_url)


# ---------------------------------------------------------------------------
# /token: authorization_code grant
# ---------------------------------------------------------------------------

def test_token_exchange_happy_path(issue_tokens):
    tokens, user_id, _client_id = issue_tokens()
    assert tokens["token_type"].lower() == "bearer"
    assert tokens["access_token"].startswith("crt_")
    assert tokens["refresh_token"].startswith("crr_")
    assert tokens["expires_in"] == settings.access_token_ttl

    row = get_token_row(tokens["access_token"])
    assert row is not None
    assert row.user_id == user_id
    assert row.revoked is False
    # Only hashes are stored
    assert tokens["access_token"] not in (row.token_hash, row.refresh_token_hash)
    assert row.token_hash == sha256_hex(tokens["access_token"])


def test_pkce_verify_failure(client, make_user, register_client, mint_auth_code):
    user_id = make_user()
    registration = register_client()
    _verifier, challenge = make_pkce_pair()
    code = mint_auth_code(user_id, registration["client_id"], challenge)
    wrong_verifier, _ = make_pkce_pair()
    resp = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_CALLBACK,
            "client_id": registration["client_id"],
            "code_verifier": wrong_verifier,
        },
    )
    assert resp.status_code in (400, 401)
    body = resp.json()
    assert body["error"] == "invalid_grant"
    assert "code_verifier" in (body.get("error_description") or "")


def test_expired_auth_code_rejected(client, make_user, register_client,
                                    mint_auth_code):
    user_id = make_user()
    registration = register_client()
    verifier, challenge = make_pkce_pair()
    code = mint_auth_code(
        user_id, registration["client_id"], challenge, expires_in_seconds=-30
    )
    resp = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_CALLBACK,
            "client_id": registration["client_id"],
            "code_verifier": verifier,
        },
    )
    assert resp.status_code in (400, 401)
    assert resp.json()["error"] == "invalid_grant"


def test_auth_code_is_single_use(client, make_user, register_client,
                                 mint_auth_code):
    user_id = make_user()
    registration = register_client()
    verifier, challenge = make_pkce_pair()
    code = mint_auth_code(user_id, registration["client_id"], challenge)
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": CLAUDE_CALLBACK,
        "client_id": registration["client_id"],
        "code_verifier": verifier,
    }
    first = client.post("/token", data=form)
    assert first.status_code == 200
    second = client.post("/token", data=form)
    assert second.status_code in (400, 401)
    assert second.json()["error"] == "invalid_grant"


def test_subscription_lapsed_user_refused_at_token_issuance(
    client, make_user, register_client, mint_auth_code
):
    user_id = make_user(
        email="lapsed@example.com",
        plan_tier="solo",
        subscription_status="canceled",
    )
    registration = register_client()
    verifier, challenge = make_pkce_pair()
    code = mint_auth_code(user_id, registration["client_id"], challenge)
    resp = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_CALLBACK,
            "client_id": registration["client_id"],
            "code_verifier": verifier,
        },
    )
    assert resp.status_code in (400, 401)
    body = resp.json()
    assert body["error"] == "invalid_grant"
    assert "subscription" in body["error_description"].lower()


# ---------------------------------------------------------------------------
# /token: refresh_token grant with rotation
# ---------------------------------------------------------------------------

def test_refresh_rotation_invalidates_old_tokens(client, issue_tokens):
    tokens, _user_id, client_id = issue_tokens()

    refresh = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        },
    )
    assert refresh.status_code == 200, refresh.text
    new_tokens = refresh.json()
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The old refresh token is dead: replaying it yields invalid_grant
    replay = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        },
    )
    assert replay.status_code in (400, 401)
    assert replay.json()["error"] == "invalid_grant"

    # And the old ACCESS token died with the rotation too
    old_row = get_token_row(tokens["access_token"])
    assert old_row.revoked is True


# ---------------------------------------------------------------------------
# Bearer auth on the MCP endpoint
# ---------------------------------------------------------------------------

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

LIST_TOOLS_BODY = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


def test_missing_bearer_gets_401_with_resource_metadata_header(client):
    resp = client.post("/mcp", json=LIST_TOOLS_BODY, headers=MCP_HEADERS)
    assert resp.status_code == 401
    expected = (
        'Bearer resource_metadata='
        '"http://localhost:8300/.well-known/oauth-protected-resource"'
    )
    assert resp.headers.get("www-authenticate") == expected


def test_revoked_bearer_gets_401_with_resource_metadata_header(
    client, issue_tokens
):
    tokens, _user_id, client_id = issue_tokens()
    access_token = tokens["access_token"]

    # Sanity: the token works before revocation
    ok = client.post(
        "/mcp",
        json=LIST_TOOLS_BODY,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {access_token}"},
    )
    assert ok.status_code == 200

    # NOTE: the SDK's RevocationRequest model requires the client_secret KEY
    # to be present (public clients send it empty)
    revoke = client.post(
        "/revoke",
        data={"token": access_token, "client_id": client_id,
              "client_secret": ""},
    )
    assert revoke.status_code == 200

    resp = client.post(
        "/mcp",
        json=LIST_TOOLS_BODY,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401
    assert (
        resp.headers.get("www-authenticate")
        == 'Bearer resource_metadata='
           '"http://localhost:8300/.well-known/oauth-protected-resource"'
    )


def test_expired_bearer_gets_401(client, issue_tokens):
    tokens, _user_id, _client_id = issue_tokens()
    access_token = tokens["access_token"]
    # Force-expire the row
    with session_scope() as session:
        row = (
            session.query(MCPToken)
            .filter_by(token_hash=sha256_hex(access_token))
            .one()
        )
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    resp = client.post(
        "/mcp",
        json=LIST_TOOLS_BODY,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == 401
    assert "resource_metadata" in resp.headers.get("www-authenticate", "")


# ---------------------------------------------------------------------------
# Discovery metadata
# ---------------------------------------------------------------------------

def test_authorization_server_metadata(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["issuer"].rstrip("/") == settings.mcp_issuer_url
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert "offline_access" in meta["scopes_supported"]
    assert meta["registration_endpoint"].endswith("/register")
    assert meta["revocation_endpoint"].endswith("/revoke")


def test_protected_resource_metadata_resource_is_canonical(client):
    # Root document (the URL the 401 header points at)
    root = client.get("/.well-known/oauth-protected-resource")
    assert root.status_code == 200
    assert root.json()["resource"].rstrip("/") == settings.canonical_mcp_url
    # RFC 9728 path-scoped document
    scoped = client.get("/.well-known/oauth-protected-resource/mcp")
    assert scoped.status_code == 200
    assert scoped.json()["resource"].rstrip("/") == settings.canonical_mcp_url


def test_health_route_is_unauthenticated(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
