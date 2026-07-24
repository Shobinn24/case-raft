"""Phase 2 tool tests: mocked Clio HTTP, truncation flags, audit rows,
timezone handling, and prompts."""

from caseraft_mcp.db import AuditLog, session_scope

from . import clio_fixtures as fx


# ---------------------------------------------------------------------------
# list_matters
# ---------------------------------------------------------------------------

def test_list_matters_compact_rows(mcp_session, clio):
    clio.set("matters.json", fx.matters_list(5))
    session = mcp_session()
    result = session.call_tool("list_matters", {"limit": 25})
    assert result["truncated"] is False
    assert result["count"] == 5
    first = result["matters"][0]
    assert first == {
        "id": 9001,
        "display_number": "2026-001",
        "description": "Williams v. Metro Transit Authority",
        "client": "Sarah Williams",
        "status": "open",
        "practice_area": "Personal Injury",
    }
    # Compact rows only: no attorney, no billing fields
    assert "responsible_attorney" not in first
    # Clio was asked for open matters
    params = clio.calls_to("matters.json")[0][2]
    assert params["status"] == "open"


def test_list_matters_truncates_and_flags(mcp_session, clio):
    clio.set("matters.json", fx.matters_list(6))
    session = mcp_session()
    result = session.call_tool("list_matters", {"limit": 5})
    assert result["count"] == 5
    assert result["truncated"] is True


def test_list_matters_passes_query_and_status(mcp_session, clio):
    clio.set("matters.json", fx.matters_list(1))
    session = mcp_session()
    session.call_tool("list_matters", {"query": "Williams", "status": "closed"})
    params = clio.calls_to("matters.json")[0][2]
    assert params["query"] == "Williams"
    assert params["status"] == "closed"


# ---------------------------------------------------------------------------
# get_matter
# ---------------------------------------------------------------------------

def test_get_matter_detail_contacts_and_billing(mcp_session, clio):
    clio.set("matters/9001.json", fx.matter_detail(9001))
    clio.set("related_contacts.json", fx.related_contacts())
    clio.set("activities.json", fx.matter_activities(9001))
    clio.set("bills.json", fx.matter_bills())
    session = mcp_session()

    result = session.call_tool("get_matter", {"matter_id": 9001})

    assert result["display_number"] == "2026-001"
    assert result["practice_area"] == "Personal Injury"
    assert result["client"]["name"] == "Sarah Williams"

    rc = result["related_contacts"]
    assert [c["name"] for c in rc["opposing_counsel"]] == ["John Doe (Attorney)"]
    assert [c["name"] for c in rc["opposing_parties"]] == ["Metro Transit Authority"]
    assert [c["name"] for c in rc["court"]] == ["Hon. Rachel Kim"]
    # The matter client is not repeated in related contacts
    all_names = [c["name"] for group in rc.values() for c in group]
    assert "Sarah Williams" not in all_names

    summary = result["billing_summary"]
    assert summary == {
        "total_billed": 3500.0,
        "total_paid": 1500.0,
        "outstanding_balance": 2000.0,
        "total_hours": 3.5,
        "billable_hours": 2.5,
        "non_billable_hours": 1.0,
        "invoice_count": 1,
        "time_entry_count": 2,
    }


def test_get_matter_not_found_is_tool_error(mcp_session, clio):
    clio.set("matters/999.json", {"data": None})
    session = mcp_session()
    message = session.call_tool("get_matter", {"matter_id": 999},
                                expect_error=True)
    assert "not found" in message.lower()
    with session_scope() as db:
        row = (
            db.query(AuditLog)
            .filter_by(action="mcp.tool.get_matter")
            .one()
        )
        assert "status=error" in row.detail


# ---------------------------------------------------------------------------
# contacts
# ---------------------------------------------------------------------------

def test_search_contacts_rows_and_truncation(mcp_session, clio):
    clio.set("contacts.json", fx.contacts_search())
    session = mcp_session()
    result = session.call_tool("search_contacts", {"query": "Sarah", "limit": 2})
    assert result["count"] == 2
    assert result["truncated"] is True
    assert result["contacts"][0] == {
        "id": 101,
        "name": "Sarah Williams",
        "type": "Person",
        "email": "sarah@example.com",
        "phone": "(555) 123-4567",
        "company": None,
        "is_client": True,
    }
    params = clio.calls_to("contacts.json")[0][2]
    assert params["query"] == "Sarah"


def test_get_contact_detail(mcp_session, clio):
    clio.set("contacts/101.json", fx.contact_detail(101))
    session = mcp_session()
    result = session.call_tool("get_contact", {"contact_id": 101})
    assert result["name"] == "Sarah Williams"
    assert result["is_client"] is True
    assert result["emails"] == [{"address": "sarah@example.com", "label": "Work"}]
    assert result["addresses"][0]["city"] == "Boston"


# ---------------------------------------------------------------------------
# firm_productivity
# ---------------------------------------------------------------------------

def test_firm_productivity_totals_and_rates(mcp_session, clio):
    clio.set("users.json", fx.firm_users())
    clio.set("activities.json", {"data": fx.firm_activities()})
    clio.set("bills.json", {"data": fx.firm_bills()})
    clio.set("practice_areas.json", fx.practice_areas())
    session = mcp_session()

    result = session.call_tool(
        "firm_productivity", {"start": "2026-06-01", "end": "2026-06-30"})

    # June 2026 has 22 working days -> 176 target hours per employee
    assert result["target_hours_per_employee"] == 176.0

    by_name = {e["name"]: e for e in result["employees"]}
    shobin = by_name["Shobin Clark"]
    assert shobin["total_hours"] == 12.0
    assert shobin["billable_hours"] == 10.0
    assert shobin["non_billable_hours"] == 2.0
    assert shobin["billed_amount"] == 3500.0
    # Paid bill 601 (3500) on matter 9001 attributes fully to Shobin
    assert shobin["collected_revenue"] == 3500.0
    assert shobin["realization_rate"] == 1.0

    ana = by_name["Ana Torres"]
    assert ana["billable_hours"] == 9.0
    assert ana["write_off_hours"] == 1.0

    totals = result["firm_totals"]
    assert totals["total_hours"] == 21.0
    assert totals["billable_hours"] == 19.0
    assert totals["billed_amount"] == 5500.0
    assert totals["collected_revenue"] == 3500.0
    assert totals["outstanding_balance"] == 3600.0
    assert totals["realization_rate"] == round(5500 / 5750, 4)
    assert totals["collection_rate"] == round(3500 / 5500, 4)

    aging = result["invoice_aging"]
    assert aging["current"]["total"] == 1200.0
    assert aging["31_60"]["total"] == 2400.0
    assert aging["over_90"]["count"] == 0


# ---------------------------------------------------------------------------
# outstanding_revenue
# ---------------------------------------------------------------------------

def test_outstanding_revenue_buckets_by_practice_area(mcp_session, clio):
    clio.set("bills.json", {"data": fx.firm_bills()})
    clio.set("practice_areas.json", fx.practice_areas())
    session = mcp_session()

    result = session.call_tool(
        "outstanding_revenue", {"start": "2026-06-01", "end": "2026-06-30"})

    # Collected: bill 601 paid 3500, 18 days issued-to-paid -> 1-30 bucket,
    # practice area resolved through the id lookup (Clio nests only the id)
    collected = result["collected"]
    assert collected["rows"] == [
        {"practice_area": "Personal Injury", "1_30": 3500.0, "31_60": 0.0,
         "61_90": 0.0, "91_plus": 0.0, "total": 3500.0},
    ]

    outstanding = result["outstanding"]
    by_pa = {row["practice_area"]: row for row in outstanding["rows"]}
    assert by_pa["Corporate"]["31_60"] == 2400.0    # 45 days old at 06-30
    assert by_pa["Personal Injury"]["1_30"] == 1200.0
    assert outstanding["totals"]["total"] == 3600.0


# ---------------------------------------------------------------------------
# trust_balances
# ---------------------------------------------------------------------------

def test_trust_balances_no_allowlist_only_plan_gate(mcp_session, clio):
    clio.set("matters.json", {"data": fx.trust_matters()})
    # A regular PAID user (not whitelisted, not the trust-report email)
    session = mcp_session(email="anyfirm@example.com", plan_tier="solo",
                          subscription_status="active")

    result = session.call_tool("trust_balances", {})

    assert result["total_clients_below"] == 4
    assert result["total_deficit"] == 24100.0
    assert result["tcp_count"] == 3
    assert result["non_tcp_count"] == 1
    # Sorted by largest deficit; above-threshold client excluded
    names = [r["client_name"] for r in result["clients_below_threshold"]]
    assert names == ["Acme Corp", "Sarah Williams",
                     "Greenfield Enterprises", "David Nguyen"]
    assert "Maria Rivera" not in names
    assert result["clients_below_threshold"][0]["amount_below"] == 12900.0


# ---------------------------------------------------------------------------
# daily_digest
# ---------------------------------------------------------------------------

def test_daily_digest_contents_and_timezone(mcp_session, clio):
    clio.set("tasks.json", fx.tasks_due())
    clio.set("calendar_entries.json", fx.calendar_entries())
    clio.set("bills.json", {"data": fx.firm_bills()})
    session = mcp_session(email="tzuser@example.com",
                          timezone="Eastern Time (US & Canada)")

    result = session.call_tool("daily_digest", {"date": "2026-07-24"})

    assert result["date"] == "2026-07-24"
    assert result["timezone"] == "America/New_York"

    summary = result["summary"]
    assert summary["tasks_open"] == 2
    assert summary["tasks_overdue"] == 1
    assert summary["calendar_entries"] == 2
    assert summary["unpaid_bills"] == 2
    assert summary["outstanding_balance"] == 3600.0

    overdue = [t for t in result["tasks"] if t["overdue"]]
    assert [t["id"] for t in overdue] == [801]

    # The calendar window was requested in the user's LOCAL day (EDT in July)
    params = clio.calls_to("calendar_entries.json")[0][2]
    assert params["from"] == "2026-07-24T00:00:00-04:00"
    assert params["to"] == "2026-07-25T00:00:00-04:00"

    # Tasks were filtered to open items due by the target date
    task_params = clio.calls_to("tasks.json")[0][2]
    assert task_params["complete"] == "false"
    assert task_params["due_at_to"] == "2026-07-24"


def test_daily_digest_defaults_to_today_in_user_tz(mcp_session, clio):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    clio.set("tasks.json", {"data": []})
    clio.set("calendar_entries.json", {"data": []})
    clio.set("bills.json", {"data": []})
    session = mcp_session(email="hi@example.com",
                          timezone="Pacific Time (US & Canada)")

    result = session.call_tool("daily_digest", {})
    expected = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    assert result["date"] == expected
    assert result["timezone"] == "America/Los_Angeles"


def test_daily_digest_unknown_timezone_falls_back_to_utc(mcp_session, clio):
    clio.set("tasks.json", {"data": []})
    clio.set("calendar_entries.json", {"data": []})
    clio.set("bills.json", {"data": []})
    session = mcp_session(email="whom@example.com", timezone="Narnia Time")
    result = session.call_tool("daily_digest", {"date": "2026-07-24"})
    assert result["timezone"] == "UTC"


def test_daily_digest_degrades_when_tasks_and_calendar_forbidden(mcp_session, clio):
    # Clio 403s (missing app scopes) must degrade those sections, not the
    # whole digest: bills and the summary still ship, with notes.
    clio.set_forbidden("tasks.json")
    clio.set_forbidden("calendar_entries.json")
    clio.set("bills.json", {"data": [
        {"id": 1, "number": "INV-1", "issued_at": "2026-07-01",
         "due_at": "2026-07-15", "state": "awaiting_payment", "balance": 500.0},
    ]})
    session = mcp_session(email="scoped@example.com", timezone="Eastern Time (US & Canada)")
    result = session.call_tool("daily_digest", {"date": "2026-07-24"})
    assert result["tasks_available"] is False
    assert result["calendar_available"] is False
    assert result["tasks"] == [] and result["calendar_entries"] == []
    assert "permission" in result["tasks_note"]
    assert "permission" in result["calendar_note"]
    assert result["summary"]["tasks_open"] is None
    assert result["summary"]["calendar_entries"] is None
    assert result["summary"]["unpaid_bills"] == 1
    assert result["summary"]["outstanding_balance"] == 500.0
    assert result["unpaid_bills"][0]["number"] == "INV-1"


def test_daily_digest_partial_forbidden_only_hits_that_section(mcp_session, clio):
    clio.set_forbidden("tasks.json")
    clio.set("calendar_entries.json", {"data": [
        {"id": 9, "summary": "Hearing", "start_at": "2026-07-24T14:00:00Z",
         "end_at": "2026-07-24T15:00:00Z", "all_day": False,
         "location": "Court", "matter": {"display_number": "2026-001"}},
    ]})
    clio.set("bills.json", {"data": []})
    session = mcp_session(email="partial@example.com", timezone="Eastern Time (US & Canada)")
    result = session.call_tool("daily_digest", {"date": "2026-07-24"})
    assert result["tasks_available"] is False
    assert result["calendar_available"] is True
    assert result["summary"]["calendar_entries"] == 1
    assert result["calendar_entries"][0]["summary"] == "Hearing"
    assert "calendar_note" not in result


# ---------------------------------------------------------------------------
# audit logging
# ---------------------------------------------------------------------------

def test_tool_calls_write_audit_rows_without_pii(mcp_session, clio):
    clio.set("matters.json", fx.matters_list(2))
    session = mcp_session()
    session.call_tool("list_matters", {"query": "Williams", "limit": 5})

    with session_scope() as db:
        row = (
            db.query(AuditLog)
            .filter_by(action="mcp.tool.list_matters")
            .one()
        )
        assert row.user_id == session.user_id
        assert row.resource_type == "mcp_tool"
        assert row.resource_id == "list_matters"
        assert "status=ok" in row.detail
        assert "limit=5" in row.detail
        # Argument SHAPES only: the search text itself never lands in audit
        assert "Williams" not in row.detail
        assert "query_len=8" in row.detail


def test_whoami_writes_audit_row(mcp_session, clio):
    clio.set("who_am_i.json", {"data": {"name": "A", "email": "a@b.c",
                                        "account": {"name": "Firm"}}})
    session = mcp_session()
    session.call_tool("whoami", {})
    with session_scope() as db:
        assert (
            db.query(AuditLog).filter_by(action="mcp.tool.whoami").count() == 1
        )


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

def test_prompts_are_listed(mcp_session):
    session = mcp_session()
    result = session.rpc("prompts/list")
    names = {p["name"] for p in result["prompts"]}
    assert names == {"morning_digest", "status_update_email", "intake_summary"}


def test_status_update_email_prompt_renders_with_argument(mcp_session):
    session = mcp_session()
    result = session.rpc(
        "prompts/get",
        {"name": "status_update_email", "arguments": {"matter": "2026-001"}},
    )
    text = result["messages"][0]["content"]["text"]
    assert "2026-001" in text
    assert "get_matter" in text
    assert "draft" in text.lower()


def test_morning_digest_prompt_mentions_daily_digest(mcp_session):
    session = mcp_session()
    result = session.rpc("prompts/get", {"name": "morning_digest"})
    text = result["messages"][0]["content"]["text"]
    assert "daily_digest" in text
