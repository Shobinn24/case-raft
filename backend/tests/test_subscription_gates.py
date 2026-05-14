"""Subscription gate enforcement tests.

Covers the `require_subscription` decorator (and the legacy
`_require_subscription` helper) — specifically:
  - Free/unsubscribed users get 403
  - Active paid users pass
  - Admins bypass without needing a paid sub
  - Whitelisted users bypass without needing a paid sub
  - The `/api/cases` routes are now gated (audit finding 2026-05-14, P0 #2)
"""


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


# ---------------------------------------------------------------------------
# /api/cases gate (new 2026-05-14)
# ---------------------------------------------------------------------------

def test_cases_list_blocks_free_user(client, make_user):
    user = make_user(plan_tier="free", subscription_status="free")
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code == 403
    assert resp.get_json().get("upgrade") is True


def test_cases_detail_blocks_free_user(client, make_user):
    user = make_user(plan_tier="free", subscription_status="free")
    _login(client, user.id)

    resp = client.get("/api/cases/123")
    assert resp.status_code == 403
    assert resp.get_json().get("upgrade") is True


def test_cases_blocks_past_due(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="past_due")
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code == 403


def test_cases_blocks_canceled(client, make_user):
    user = make_user(plan_tier="free", subscription_status="canceled")
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code == 403


def test_cases_blocks_unauthenticated(client):
    # No session at all
    resp = client.get("/api/cases")
    assert resp.status_code == 401


def test_cases_allows_active_solo(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="active")
    _login(client, user.id)

    # Clio call will fail (stub tokens) but the gate must pass first. Anything
    # not 401/403/upgrade is acceptable here.
    resp = client.get("/api/cases")
    assert resp.status_code != 403
    assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Admin bypass (new 2026-05-14)
# ---------------------------------------------------------------------------

def test_admin_user_bypasses_subscription_gate(client, make_user):
    """Admins (by email in ADMIN_EMAILS or is_admin=True) get paid features
    without needing a real subscription. Used for support / demo / debug."""
    user = make_user(
        email="shobinn24@gmail.com",  # listed in default ADMIN_EMAILS
        plan_tier="free",
        subscription_status="free",
    )
    _login(client, user.id)

    resp = client.get("/api/cases")
    # Should pass the gate (no 403). Real call may fail downstream, but not at
    # the gate.
    assert resp.status_code != 403


def test_admin_flag_user_bypasses_subscription_gate(client, make_user, app):
    """A user with is_admin=True in DB (but NOT in ADMIN_EMAILS) also bypasses."""
    from app.extensions import db

    user = make_user(
        email="random@example.com",
        plan_tier="free",
        subscription_status="free",
    )
    user.is_admin = True
    db.session.commit()
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code != 403


def test_admin_bypasses_tier_gate_to_firm(client, make_user):
    """Admins should be treated as firm-tier for tier-gated features."""
    user = make_user(
        email="shobinn24@gmail.com",
        plan_tier="free",
        subscription_status="free",
    )
    _login(client, user.id)

    resp = client.post(
        "/api/reports/generate-batch",
        json={"case_ids": []},  # empty list -> 400, past the tier gate
    )
    # Pre-fix, this 403'd because admin didn't bypass the tier gate.
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Whitelist bypass (existing — regression coverage)
# ---------------------------------------------------------------------------

def test_whitelisted_user_bypasses_subscription_gate(client, make_user):
    """Whitelisted users (Sarah Rhoades etc.) get paid features without a sub."""
    user = make_user(
        email="srhoades@trustice.us",  # in default WHITELISTED_EMAILS
        plan_tier="free",
        subscription_status="free",
    )
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code != 403


def test_whitelisted_domain_user_bypasses(client, make_user):
    """Anyone @trustice.us bypasses (domain-level whitelist)."""
    user = make_user(
        email="someone@trustice.us",
        plan_tier="free",
        subscription_status="free",
    )
    _login(client, user.id)

    resp = client.get("/api/cases")
    assert resp.status_code != 403
