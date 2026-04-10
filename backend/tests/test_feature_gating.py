"""Tier-gated endpoints must 403 for solo subscribers.

Verifies the fix for issue #7 from the review: generate-batch,
export-accounting, firm_productivity, and revenue_by_practice_area
were all checking only is_paid (letting solo in) when they should
have been Team+.
"""


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def test_batch_reports_blocks_solo(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="active")
    _login(client, user.id)

    resp = client.post(
        "/api/reports/generate-batch",
        json={"case_ids": [1, 2]},
    )
    assert resp.status_code == 403
    assert resp.get_json().get("upgrade") is True


def test_batch_reports_allows_team(client, make_user, monkeypatch):
    user = make_user(plan_tier="team", subscription_status="active")
    _login(client, user.id)

    # We don't care about actual report generation — just that tier gating
    # lets the request past the 403. The Clio call will fail and we'll get
    # a 500/502 or a reports-level error, any of which is fine: the important
    # thing is the response is not 403.
    resp = client.post(
        "/api/reports/generate-batch",
        json={"case_ids": []},  # empty list triggers a 400, past the tier check
    )
    assert resp.status_code != 403


def test_export_accounting_blocks_solo(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="active")
    _login(client, user.id)

    resp = client.post(
        "/api/reports/export-accounting",
        json={"start_date": "2026-01-01", "end_date": "2026-01-31"},
    )
    assert resp.status_code == 403


def test_firm_productivity_blocks_solo(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="active")
    _login(client, user.id)

    resp = client.post(
        "/api/reports/generate-firm",
        json={
            "report_type": "firm_productivity",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert resp.status_code == 403


def test_revenue_by_practice_area_blocks_solo(client, make_user):
    user = make_user(plan_tier="solo", subscription_status="active")
    _login(client, user.id)

    resp = client.post(
        "/api/reports/generate-firm",
        json={
            "report_type": "revenue_by_practice_area",
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
        },
    )
    assert resp.status_code == 403
