"""OAuth state must be bound to the session nonce.

Verifies the fix for issue #1 from the review: /callback must reject
any state that wasn't paired with a nonce in the current session.
"""

from itsdangerous import URLSafeTimedSerializer


def test_login_sets_session_nonce(client, app):
    resp = client.get("/auth/login")
    # It's a 302 redirect to Clio
    assert resp.status_code in (301, 302)
    with client.session_transaction() as sess:
        assert "oauth_nonce" in sess
        assert len(sess["oauth_nonce"]) > 16


def test_callback_rejects_missing_nonce(client, app):
    """A callback without a matching session nonce must be rejected,
    even if the state token is cryptographically valid."""
    s = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    forged_state = s.dumps({"nonce": "attacker-supplied-value"})

    # Note: we never called /auth/login, so the session has no oauth_nonce.
    resp = client.get(f"/auth/callback?state={forged_state}&code=fake-code")
    assert resp.status_code == 400
    body = resp.get_json()
    assert "nonce" in (body.get("error") or "").lower() or "state" in (body.get("error") or "").lower()


def test_callback_rejects_wrong_nonce(client, app):
    """Even with a session present, the callback must reject a nonce
    that doesn't match what /login stored."""
    # Seed a session nonce directly, then send a different one in the state
    with client.session_transaction() as sess:
        sess["oauth_nonce"] = "the-real-nonce"

    s = URLSafeTimedSerializer(app.config["SECRET_KEY"])
    forged_state = s.dumps({"nonce": "some-other-nonce"})

    resp = client.get(f"/auth/callback?state={forged_state}&code=fake-code")
    assert resp.status_code == 400
