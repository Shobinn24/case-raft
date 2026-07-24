"""Fixtures for the CaseRaft MCP service tests.

Env is pinned at module import (before caseraft_mcp modules load their
settings) mirroring the Flask conftest pattern. The database is a per-test
sqlite file; caseraft_mcp.db rebuilds its engine automatically when
DATABASE_URL changes, so every test starts from an empty schema.

Clio HTTP is never hit: tests that exercise the whoami tool monkeypatch
requests at the caseraft_mcp.clio_client boundary.
"""

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta

import pytest
from cryptography.fernet import Fernet

os.environ["MCP_ISSUER_URL"] = "http://localhost:8300"
os.environ["CONSENT_URL"] = "https://caseraft.com/connect/authorize"
os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ["CLIO_CLIENT_ID"] = "test-clio-client"
os.environ["CLIO_CLIENT_SECRET"] = "test-clio-secret"

from caseraft_mcp import db as db_module  # noqa: E402
from caseraft_mcp.crypto import sha256_hex  # noqa: E402
from caseraft_mcp.db import MCPAuthCode, MCPToken, User, session_scope  # noqa: E402

CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/mcp-test.db")
    db_module.reset_engine()
    db_module.create_all()
    yield
    db_module.reset_engine()


@pytest.fixture
def client():
    """Starlette TestClient against the full app (runs lifespan)."""
    from starlette.testclient import TestClient

    from caseraft_mcp.server import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user():
    def _factory(email="lawyer@example.com", plan_tier="solo",
                 subscription_status="active",
                 clio_access_token="clio-access-stub",
                 clio_refresh_token="clio-refresh-stub",
                 timezone=None):
        with session_scope() as session:
            user = User(
                email=email,
                clio_access_token=clio_access_token,
                clio_refresh_token=clio_refresh_token,
                token_expires_at=datetime.utcnow() + timedelta(hours=1),
                plan_tier=plan_tier,
                subscription_status=subscription_status,
                timezone=timezone,
            )
            session.add(user)
            session.flush()
            user_id = user.id
        return user_id

    return _factory


@pytest.fixture
def register_client(client):
    def _register(redirect_uris=None):
        resp = client.post(
            "/register",
            json={
                "client_name": "Claude",
                "redirect_uris": redirect_uris or [CLAUDE_CALLBACK],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _register


def make_pkce_pair():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@pytest.fixture
def mint_auth_code():
    """Simulate what the Flask consent page does: store a hashed code row."""

    def _mint(user_id, client_id, code_challenge,
              redirect_uri=CLAUDE_CALLBACK,
              scopes="clio:read offline_access",
              expires_in_seconds=600, used=False):
        code = "crc_" + secrets.token_urlsafe(43)
        with session_scope() as session:
            session.add(
                MCPAuthCode(
                    code_hash=sha256_hex(code),
                    user_id=user_id,
                    client_id=client_id,
                    code_challenge=code_challenge,
                    scopes=scopes,
                    redirect_uri=redirect_uri,
                    expires_at=datetime.utcnow()
                    + timedelta(seconds=expires_in_seconds),
                    used=used,
                )
            )
        return code

    return _mint


@pytest.fixture
def issue_tokens(client, make_user, register_client, mint_auth_code):
    """Full happy-path helper: register + consent + token exchange.
    Returns (token_response_json, user_id, client_id)."""

    def _issue(**user_kwargs):
        user_id = make_user(**user_kwargs)
        registration = register_client()
        client_id = registration["client_id"]
        verifier, challenge = make_pkce_pair()
        code = mint_auth_code(user_id, client_id, challenge)
        resp = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": CLAUDE_CALLBACK,
                "client_id": client_id,
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 200, resp.text
        return resp.json(), user_id, client_id

    return _issue


def get_token_row(access_token):
    with session_scope() as session:
        return (
            session.query(MCPToken)
            .filter_by(token_hash=sha256_hex(access_token))
            .one_or_none()
        )


# ---------------------------------------------------------------------------
# Clio HTTP mock + MCP protocol helpers (Phase 2 tool tests)
# ---------------------------------------------------------------------------

class FakeClioResponse:
    headers = {}
    url = ""
    text = ""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.ok = status < 400
        self.reason = "OK" if status < 400 else "Forbidden" if status == 403 else "Error"

    def json(self):
        return self._payload


class _ForbiddenMarker:
    pass


class ClioMock:
    """Routes Clio endpoint suffixes to canned payloads and records calls."""

    def __init__(self):
        self.routes = {}
        self.calls = []  # list of (method, url, params)

    def set(self, endpoint_suffix, payload):
        """payload: dict, or callable(params) -> dict."""
        self.routes[endpoint_suffix] = payload

    def set_forbidden(self, endpoint_suffix):
        """Simulate Clio's 403 ForbiddenError (missing app scope)."""
        self.routes[endpoint_suffix] = _ForbiddenMarker()

    def calls_to(self, endpoint_suffix):
        return [c for c in self.calls if endpoint_suffix in c[1]]

    def request(self, method, url, params=None, headers=None, timeout=None):
        self.calls.append((method, url, dict(params or {})))
        for suffix, payload in self.routes.items():
            if suffix in url:
                if isinstance(payload, _ForbiddenMarker):
                    return FakeClioResponse(
                        {"error": {"type": "ForbiddenError",
                                   "message": "User is forbidden from taking that action"}},
                        status=403,
                    )
                data = payload(params or {}) if callable(payload) else payload
                return FakeClioResponse(data)
        return FakeClioResponse({"data": []})


@pytest.fixture
def clio(monkeypatch):
    mock = ClioMock()
    monkeypatch.setattr(
        "caseraft_mcp.clio_client.requests.request", mock.request
    )
    return mock


MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


@pytest.fixture
def mcp_session(client, issue_tokens):
    """Issues tokens for a paid user and returns helpers for MCP calls.

    Returns an object with .user_id, .call_tool(name, arguments) returning
    the structured result dict (raising on tool error), and .rpc(method,
    params) for raw JSON-RPC access (tools/list, prompts/*)."""
    import json as _json

    class Session:
        def __init__(self, **user_kwargs):
            tokens, self.user_id, self.client_id = issue_tokens(**user_kwargs)
            self.access_token = tokens["access_token"]

        def rpc(self, method, params=None):
            body = {"jsonrpc": "2.0", "id": 1, "method": method}
            if params is not None:
                body["params"] = params
            resp = client.post(
                "/mcp",
                json=body,
                headers={**MCP_HEADERS,
                         "Authorization": f"Bearer {self.access_token}"},
            )
            assert resp.status_code == 200, resp.text
            payload = resp.json()
            assert "error" not in payload, payload
            return payload["result"]

        def call_tool(self, name, arguments=None, expect_error=False):
            result = self.rpc(
                "tools/call",
                {"name": name, "arguments": arguments or {}},
            )
            if expect_error:
                assert result.get("isError"), result
                return result["content"][0]["text"]
            assert not result.get("isError"), result
            structured = result.get("structuredContent")
            if structured is None:
                structured = _json.loads(result["content"][0]["text"])
            return structured

    return Session

