"""End-to-end tool test: bearer token -> user row -> decrypted Clio token ->
mocked Clio HTTP -> whoami result."""

import json

from sqlalchemy import text

from caseraft_mcp.crypto import decrypt_token
from caseraft_mcp.db import session_scope

MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


class FakeClioResponse:
    status_code = 200
    ok = True
    headers = {}

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_whoami_returns_name_email_firm(client, issue_tokens, monkeypatch):
    tokens, user_id, _client_id = issue_tokens(
        email="shameka@trustice.us",
        clio_access_token="clio-access-real",
    )

    captured = {}

    def fake_request(method, url, params=None, headers=None, timeout=None):
        captured["method"] = method
        captured["url"] = url
        captured["auth"] = headers.get("Authorization")
        return FakeClioResponse(
            {
                "data": {
                    "id": 42,
                    "name": "Shameka Rhoades",
                    "email": "shameka@trustice.us",
                    "account": {"id": 7, "name": "Trustice Law"},
                }
            }
        )

    monkeypatch.setattr(
        "caseraft_mcp.clio_client.requests.request", fake_request
    )

    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "whoami", "arguments": {}},
        },
        headers={**MCP_HEADERS, "Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    result = payload["result"]
    assert not result.get("isError"), result

    structured = result.get("structuredContent")
    if structured is None:
        structured = json.loads(result["content"][0]["text"])
    assert structured == {
        "name": "Shameka Rhoades",
        "email": "shameka@trustice.us",
        "firm": "Trustice Law",
    }

    # The Clio call used the DECRYPTED per-user token against who_am_i
    assert captured["auth"] == "Bearer clio-access-real"
    assert captured["url"].endswith("users/who_am_i.json")

    # And the token really was stored encrypted at rest (raw SQL bypasses
    # the EncryptedText type decorator, which would decrypt on read)
    with session_scope() as session:
        stored = session.execute(
            text("SELECT clio_access_token FROM users WHERE id = :id"),
            {"id": user_id},
        ).scalar_one()
    assert stored != "clio-access-real"
    assert decrypt_token(stored) == "clio-access-real"


def test_tools_list_shows_whoami(client, issue_tokens):
    tokens, _user_id, _client_id = issue_tokens()
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={**MCP_HEADERS, "Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert resp.status_code == 200
    tools = resp.json()["result"]["tools"]
    assert any(tool["name"] == "whoami" for tool in tools)
