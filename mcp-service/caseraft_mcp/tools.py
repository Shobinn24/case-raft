"""MCP tools and prompts for CaseRaft (Phase 2, all read-only).

Every tool:
  * resolves the bearer token to a CaseRaft user (same path as whoami),
  * talks to Clio through the ported ClioAPIClient (auto-refresh included),
  * returns plain JSON-serializable dicts with capped lists and a
    "truncated": true flag when a cap was hit,
  * writes one audit_logs row (action "mcp.tool.<name>") whose detail
    contains argument SHAPES only, never client PII (no names, no search
    text, no descriptions).

List caps: matters 100, contacts 25, digest lists 50. Results stay far
below the ~150k char tool-result budget from the build plan.
"""

import logging
from datetime import date as date_cls, datetime, timedelta, timezone

import requests
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from .audit import record_audit, summarize_args
from .clio_client import ClioAPIClient
from .computations import (
    Case,
    FirmProductivityData,
    RevenueByPracticeArea,
    TrustManagementData,
)
from .db import User, session_scope

logger = logging.getLogger(__name__)

MATTERS_CAP = 100
CONTACTS_CAP = 25
DIGEST_CAP = 50

# Clio stores Rails-style zone names (e.g. "Eastern Time (US & Canada)").
# Map the common ones to IANA; anything unmapped is tried as an IANA name
# and falls back to UTC.
RAILS_TZ_MAP = {
    "Eastern Time (US & Canada)": "America/New_York",
    "Central Time (US & Canada)": "America/Chicago",
    "Mountain Time (US & Canada)": "America/Denver",
    "Pacific Time (US & Canada)": "America/Los_Angeles",
    "Arizona": "America/Phoenix",
    "Alaska": "America/Anchorage",
    "Hawaii": "Pacific/Honolulu",
    "Atlantic Time (Canada)": "America/Halifax",
    "UTC": "UTC",
}


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

def _resolve_user():
    """Bearer token -> CaseRaft user + ready-to-use Clio client."""
    token = get_access_token()
    user_id = (getattr(token, "claims", None) or {}).get("user_id")
    if user_id is None and token.subject:
        user_id = token.subject
    if user_id is None:
        raise ToolError("Could not resolve the CaseRaft user for this token")

    with session_scope() as session:
        user = session.get(User, int(user_id))
        if user is None:
            raise ToolError("CaseRaft account not found; reconnect the connector")
        return SimpleNamespace(
            id=user.id,
            email=user.email,
            timezone=user.timezone,
            clio=ClioAPIClient(
                user.clio_access_token,   # EncryptedText decrypted on read
                user.clio_refresh_token,
                user.token_expires_at,
                user.id,
            ),
        )


def _run(tool_name, args_summary, fn):
    """Resolve user, execute, audit. args_summary must be PII-free."""
    user = _resolve_user()
    detail = summarize_args(args_summary)

    def _audit(status):
        record_audit(
            f"mcp.tool.{tool_name}",
            user_id=user.id,
            user_email=user.email,
            resource_type="mcp_tool",
            resource_id=tool_name,
            detail=f"{detail} status={status}".strip(),
        )

    try:
        result = fn(user)
    except ToolError:
        _audit("error")
        raise
    except Exception as exc:
        _audit("error")
        logger.exception("Tool %s failed", tool_name)
        # Do not leak Clio error bodies (may echo request details) to the model
        raise ToolError(
            f"{tool_name} failed ({type(exc).__name__}); try again or "
            "reconnect the connector"
        ) from exc
    _audit("ok")
    return result


def _cap_list(items, cap):
    if len(items) > cap:
        return items[:cap], True
    return items, False


def _iso_date_or_error(value, param):
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        raise ToolError(f"{param} must be an ISO date (YYYY-MM-DD)")


def _round(value, digits=4):
    return round(value, digits) if value is not None else None


def _tzinfo_for(tz_name):
    if not tz_name:
        return timezone.utc
    mapped = RAILS_TZ_MAP.get(tz_name)
    if mapped:
        return ZoneInfo(mapped)
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc


def _contact_row(c):
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "type": c.get("type"),
        "email": c.get("primary_email_address"),
        "phone": c.get("primary_phone_number"),
        "company": (c.get("company") or {}).get("name"),
        "is_client": c.get("is_client"),
    }


def _related_contact_row(rc):
    return {
        "id": rc.id,
        "name": rc.display_name,
        "relationship": rc.relationship_description,
        "email": rc.email or None,
        "phone": rc.phone or None,
        "company": rc.company or None,
    }


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register_tools(mcp):

    @mcp.tool
    def whoami() -> dict:
        """Confirm the connection: returns the signed-in Clio user's name,
        email, and law firm as CaseRaft sees them."""

        def impl(user):
            data = (user.clio.get_current_user() or {}).get("data", {})
            account = data.get("account") or {}
            return {
                "name": data.get("name"),
                "email": data.get("email"),
                "firm": account.get("name"),
            }

        return _run("whoami", {}, impl)

    @mcp.tool
    def list_matters(status: str | None = None, query: str | None = None,
                     limit: int = 25) -> dict:
        """List matters (compact rows). status: open, pending, or closed
        (default open). query: optional full-text search. limit: max rows
        (default 25, cap 100)."""
        cap = max(1, min(limit or 25, MATTERS_CAP))
        effective_status = status or "open"

        def impl(user):
            resp = user.clio.get_matters(
                status=effective_status,
                limit=min(cap + 1, 200),
                query=query,
            )
            rows = [
                {
                    "id": m.get("id"),
                    "display_number": m.get("display_number"),
                    "description": m.get("description"),
                    "client": (m.get("client") or {}).get("name"),
                    "status": m.get("status"),
                    "practice_area": (m.get("practice_area") or {}).get("name"),
                }
                for m in resp.get("data", [])
            ]
            rows, truncated = _cap_list(rows, cap)
            return {"matters": rows, "count": len(rows), "truncated": truncated}

        return _run(
            "list_matters",
            {"status": effective_status, "limit": cap,
             "query_len": len(query) if query else None},
            impl,
        )

    @mcp.tool
    def get_matter(matter_id: int) -> dict:
        """Full detail for one matter: core fields, client, related contacts
        grouped by role, and a billing summary."""

        def impl(user):
            data = (user.clio.get_matter(matter_id) or {}).get("data")
            if not data:
                raise ToolError(f"Matter {matter_id} not found")
            related = (user.clio.get_related_contacts(matter_id) or {}).get("data", [])
            bills = (user.clio.get_bills(matter_id) or {}).get("data", [])
            activities = (user.clio.get_activities(matter_id) or {}).get("data", [])

            case = Case(data)
            case.set_related_contacts(related)
            case.set_billing_data(bills, activities)

            summary = case.billing_summary
            return {
                "id": case.id,
                "display_number": case.display_number,
                "description": case.description,
                "status": case.status,
                "open_date": case.open_date,
                "close_date": case.close_date,
                "pending_date": case.pending_date,
                "practice_area": case.practice_area or None,
                "matter_stage": case.matter_stage or None,
                "responsible_attorney": case.responsible_attorney or None,
                "originating_attorney": case.originating_attorney or None,
                "billable": case.billable,
                "billing_method": case.billing_method or None,
                "client": {
                    "id": case.client.id,
                    "name": case.client.name,
                    "type": case.client.type,
                    "email": case.client.email or None,
                    "phone": case.client.phone or None,
                } if case.client else None,
                "related_contacts": {
                    "opposing_parties": [_related_contact_row(c) for c in case.opposing_parties],
                    "opposing_counsel": [_related_contact_row(c) for c in case.opposing_counsel],
                    "court": [_related_contact_row(c) for c in case.court_contacts],
                    "other": [_related_contact_row(c) for c in case.other_contacts],
                },
                "billing_summary": {
                    "total_billed": summary.total_billed,
                    "total_paid": summary.total_paid,
                    "outstanding_balance": summary.outstanding_balance,
                    "total_hours": summary.total_hours,
                    "billable_hours": summary.billable_hours,
                    "non_billable_hours": summary.non_billable_hours,
                    "invoice_count": summary.invoice_count,
                    "time_entry_count": summary.time_entry_count,
                },
            }

        return _run("get_matter", {"matter_id": matter_id}, impl)

    @mcp.tool
    def search_contacts(query: str, limit: int = 10) -> dict:
        """Search contacts by name/email (Clio full-text search). limit:
        max rows (default 10, cap 25)."""
        if not query or not query.strip():
            raise ToolError("query is required")
        cap = max(1, min(limit or 10, CONTACTS_CAP))

        def impl(user):
            resp = user.clio.search_contacts(query.strip(), limit=min(cap + 1, 200))
            rows = [_contact_row(c) for c in resp.get("data", [])]
            rows, truncated = _cap_list(rows, cap)
            return {"contacts": rows, "count": len(rows), "truncated": truncated}

        return _run(
            "search_contacts",
            {"limit": cap, "query_len": len(query.strip())},
            impl,
        )

    @mcp.tool
    def get_contact(contact_id: int) -> dict:
        """Full detail for one contact: names, emails, phones, addresses,
        company, client status."""

        def impl(user):
            data = (user.clio.get_contact(contact_id) or {}).get("data")
            if not data:
                raise ToolError(f"Contact {contact_id} not found")
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "type": data.get("type"),
                "title": data.get("title"),
                "is_client": data.get("is_client"),
                "primary_email": data.get("primary_email_address"),
                "primary_phone": data.get("primary_phone_number"),
                "emails": [
                    {"address": e.get("address"), "label": e.get("name")}
                    for e in (data.get("email_addresses") or [])
                ],
                "phones": [
                    {"number": p.get("number"), "label": p.get("name")}
                    for p in (data.get("phone_numbers") or [])
                ],
                "addresses": [
                    {
                        "street": a.get("street"),
                        "city": a.get("city"),
                        "province": a.get("province"),
                        "postal_code": a.get("postal_code"),
                        "label": a.get("name"),
                    }
                    for a in (data.get("addresses") or [])
                ],
                "company": (data.get("company") or {}).get("name"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            }

        return _run("get_contact", {"contact_id": contact_id}, impl)

    @mcp.tool
    def firm_productivity(start: str, end: str) -> dict:
        """Firm productivity for a date range (ISO dates): per-employee hours
        and billable split, realization / collection / utilization rates,
        firm totals, and invoice aging."""
        _iso_date_or_error(start, "start")
        _iso_date_or_error(end, "end")

        def impl(user):
            users = (user.clio.get_users() or {}).get("data", [])
            activities = user.clio.get_all_activities(start, end)
            bills = user.clio.get_all_bills(start, end)
            pa_lookup = {
                p.get("id"): p.get("name")
                for p in (user.clio.get_practice_areas() or {}).get("data", [])
            }
            data = FirmProductivityData(start, end, users, activities, bills,
                                        practice_area_lookup=pa_lookup)
            return {
                "start": start,
                "end": end,
                "target_hours_per_employee": data.target_hours,
                "employees": [
                    {
                        "name": e.name,
                        "total_hours": _round(e.total_hours, 2),
                        "billable_hours": _round(e.billable_hours, 2),
                        "non_billable_hours": _round(e.non_billable_hours, 2),
                        "billed_amount": _round(e.total_billed_amount, 2),
                        "collected_revenue": _round(e.collected_revenue, 2),
                        "write_off_hours": _round(e.write_off_hours, 2),
                        "realization_rate": _round(e.realization_rate),
                        "collection_rate": _round(e.collection_rate),
                        "utilization_rate": _round(e.utilization_rate),
                    }
                    for e in data.employees
                ],
                "firm_totals": {
                    "total_hours": _round(data.total_hours, 2),
                    "billable_hours": _round(data.total_billable_hours, 2),
                    "non_billable_hours": _round(data.total_non_billable_hours, 2),
                    "billed_amount": _round(data.total_billed_amount, 2),
                    "collected_revenue": _round(data.total_collected_revenue, 2),
                    "total_invoiced": _round(data.total_invoiced, 2),
                    "total_paid": _round(data.total_paid, 2),
                    "outstanding_balance": _round(data.outstanding_balance, 2),
                    "realization_rate": _round(data.firm_realization_rate),
                    "collection_rate": _round(data.firm_collection_rate),
                    "utilization_rate": _round(data.firm_utilization_rate),
                },
                "invoice_aging": {
                    key: {
                        "label": bucket["label"],
                        "total": _round(bucket["total"], 2),
                        "count": bucket["count"],
                    }
                    for key, bucket in data.aging_buckets.items()
                },
            }

        return _run("firm_productivity", {"start": start, "end": end}, impl)

    @mcp.tool
    def outstanding_revenue(start: str, end: str) -> dict:
        """Collected vs outstanding revenue by practice area, split into AR
        aging buckets, for bills issued in the date range (ISO dates)."""
        _iso_date_or_error(start, "start")
        _iso_date_or_error(end, "end")

        def impl(user):
            bills = user.clio.get_all_bills_simple(start, end)
            pa_lookup = {
                p.get("id"): p.get("name")
                for p in (user.clio.get_practice_areas() or {}).get("data", [])
            }
            collected = RevenueByPracticeArea(
                bills, end, mode="collected", practice_area_lookup=pa_lookup)
            outstanding = RevenueByPracticeArea(
                bills, end, mode="outstanding", practice_area_lookup=pa_lookup)
            return {
                "start": start,
                "end": end,
                "bucket_labels": RevenueByPracticeArea.BUCKET_LABELS,
                "collected": {
                    "rows": collected.rows,
                    "totals": collected.column_totals,
                },
                "outstanding": {
                    "rows": outstanding.rows,
                    "totals": outstanding.column_totals,
                },
            }

        return _run("outstanding_revenue", {"start": start, "end": end}, impl)

    @mcp.tool
    def trust_balances() -> dict:
        """Trust account balances vs required thresholds: clients whose trust
        balance is below their Initial Trust Deposit threshold, with per-client
        deficits. Available on any paid plan (no per-user allowlist)."""

        def impl(user):
            matters = user.clio.get_matters_with_trust_data()
            data = TrustManagementData(matters)
            rows, truncated = _cap_list(data.rows, DIGEST_CAP)
            return {
                "clients_below_threshold": rows,
                "truncated": truncated,
                "total_deficit": _round(data.total_deficit, 2),
                "total_clients_below": data.total_clients_below,
                "tcp_count": data.tcp_count,
                "non_tcp_count": data.non_tcp_count,
            }

        return _run("trust_balances", {}, impl)

    @mcp.tool
    def daily_digest(date: str | None = None) -> dict:
        """One-call daily briefing: open tasks due (and overdue), calendar
        entries, and unpaid bills for a date (ISO, default today in the
        user's timezone)."""

        def impl(user):
            tzinfo = _tzinfo_for(user.timezone)
            target_str = date or datetime.now(tzinfo).date().isoformat()
            target = _iso_date_or_error(target_str, "date")

            day_start = datetime(target.year, target.month, target.day,
                                 tzinfo=tzinfo)
            day_end = day_start + timedelta(days=1)

            # Tasks and calendar require scopes the Clio app registration may
            # not have yet; a 403 there degrades that SECTION, never the whole
            # digest (bills and the summary still ship).
            def _is_forbidden(exc):
                resp = getattr(exc, "response", None)
                return resp is not None and resp.status_code == 403

            unavailable_note = (
                "Not available yet: the CaseRaft app is awaiting Clio "
                "permission for this data."
            )

            # Open tasks due on or before the target date (catches overdue)
            task_rows = []
            overdue_count = 0
            tasks_available = True
            try:
                tasks_resp = user.clio.list_tasks(
                    due_before=target_str, complete=False)
            except requests.HTTPError as exc:
                if not _is_forbidden(exc):
                    raise
                tasks_available = False
                tasks_resp = None
            for t in (tasks_resp or {}).get("data", []):
                due_at = t.get("due_at")
                overdue = bool(due_at and due_at[:10] < target_str)
                if overdue:
                    overdue_count += 1
                task_rows.append({
                    "id": t.get("id"),
                    "name": t.get("name"),
                    "due_at": due_at,
                    "priority": t.get("priority"),
                    "status": t.get("status"),
                    "assignee": (t.get("assignee") or {}).get("name"),
                    "matter": (t.get("matter") or {}).get("display_number"),
                    "overdue": overdue,
                })
            total_open_tasks = len(task_rows)
            task_rows, tasks_truncated = _cap_list(task_rows, DIGEST_CAP)

            calendar_available = True
            try:
                events_resp = user.clio.list_calendar_entries(
                    day_start.isoformat(), day_end.isoformat())
            except requests.HTTPError as exc:
                if not _is_forbidden(exc):
                    raise
                calendar_available = False
                events_resp = None
            event_rows = [
                {
                    "id": e.get("id"),
                    "summary": e.get("summary"),
                    "start_at": e.get("start_at"),
                    "end_at": e.get("end_at"),
                    "all_day": e.get("all_day"),
                    "location": e.get("location"),
                    "matter": (e.get("matter") or {}).get("display_number"),
                }
                for e in (events_resp or {}).get("data", [])
            ]
            total_events = len(event_rows)
            event_rows, events_truncated = _cap_list(event_rows, DIGEST_CAP)

            # Unpaid bills issued in the trailing year
            lookback = (target - timedelta(days=365)).isoformat()
            bills = user.clio.get_all_bills_simple(lookback, target_str)
            unpaid = [
                b for b in bills
                if b.get("state") not in ("paid", "void", "deleted")
                and (b.get("balance") or 0) > 0
            ]
            bill_rows = [
                {
                    "id": b.get("id"),
                    "number": b.get("number"),
                    "issued_at": b.get("issued_at"),
                    "due_at": b.get("due_at"),
                    "state": b.get("state"),
                    "balance": b.get("balance"),
                }
                for b in unpaid
            ]
            bill_rows, bills_truncated = _cap_list(bill_rows, DIGEST_CAP)
            outstanding_total = sum(b.get("balance") or 0 for b in unpaid)

            result = {
                "date": target_str,
                "timezone": str(tzinfo),
                "summary": {
                    "tasks_open": total_open_tasks if tasks_available else None,
                    "tasks_overdue": overdue_count if tasks_available else None,
                    "calendar_entries": total_events if calendar_available else None,
                    "unpaid_bills": len(unpaid),
                    "outstanding_balance": _round(outstanding_total, 2),
                },
                "tasks": task_rows,
                "tasks_available": tasks_available,
                "tasks_truncated": tasks_truncated,
                "calendar_entries": event_rows,
                "calendar_available": calendar_available,
                "calendar_truncated": events_truncated,
                "unpaid_bills": bill_rows,
                "bills_truncated": bills_truncated,
            }
            if not tasks_available:
                result["tasks_note"] = unavailable_note
            if not calendar_available:
                result["calendar_note"] = unavailable_note
            return result

        return _run("daily_digest", {"date": date or "today"}, impl)


# ---------------------------------------------------------------------------
# Prompts (starter skill pack; served free with the connector)
# ---------------------------------------------------------------------------

def register_prompts(mcp):

    @mcp.prompt(name="morning_digest",
                description="Start-of-day briefing from your Clio data")
    def morning_digest() -> str:
        return (
            "Please call the daily_digest tool for today, then give me a "
            "concise morning briefing:\n"
            "1. Top priorities: overdue tasks first, then tasks due today, "
            "each with its matter number.\n"
            "2. Today's schedule in time order, noting any conflicts or "
            "tight turnarounds.\n"
            "3. Money watch: number of unpaid bills and the total "
            "outstanding balance; flag anything more than 60 days old.\n"
            "Keep it under 200 words, use short bullet points, and end with "
            "the single most important thing to do first this morning."
        )

    @mcp.prompt(name="status_update_email",
                description="Draft a client-ready status update email for a matter")
    def status_update_email(matter: str) -> str:
        return (
            f"I need a status update email for the matter '{matter}'.\n"
            "First, use list_matters (with a query if needed) to find the "
            "matter, then call get_matter for its full detail.\n"
            "Then draft a professional, client-ready email that:\n"
            "1. Opens with a one-sentence summary of where the matter stands "
            "(use the matter stage and status).\n"
            "2. Notes recent progress and the next expected steps in plain "
            "English, avoiding legal jargon the client may not know.\n"
            "3. Mentions the current outstanding balance only if it is "
            "greater than zero, phrased politely.\n"
            "4. Closes with an invitation to call with questions.\n"
            "Address the client by name, keep it under 250 words, and do not "
            "invent facts that are not in the matter data. Present it as a "
            "draft for my review, not a sent email."
        )

    @mcp.prompt(name="intake_summary",
                description="Structured intake summary for a matter")
    def intake_summary(matter: str) -> str:
        return (
            f"Prepare a structured intake summary for the matter '{matter}'.\n"
            "Use list_matters to locate it, then get_matter for detail, and "
            "get_contact on the client if more contact detail would help.\n"
            "Produce this exact structure:\n"
            "- Matter: display number, description, practice area, stage.\n"
            "- Client: name, contact details, client type.\n"
            "- Key parties: opposing parties, opposing counsel, and court "
            "contacts with their roles.\n"
            "- Key dates: open date and any pending dates.\n"
            "- Billing snapshot: billing method, hours to date, billed, "
            "paid, and outstanding balance.\n"
            "- Gaps: list any fields that are missing or look incomplete so "
            "our team can follow up.\n"
            "Use only facts returned by the tools; mark anything unknown as "
            "'not on file'."
        )
