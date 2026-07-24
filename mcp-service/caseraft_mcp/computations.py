"""Computation classes ported from the Flask app (read-only, Flask-free).

Sources, copied not imported (decision 2 in the build plan: copy is fine for
MVP; extract a shared package when it hurts):

  * backend/app/services/case.py       Case, Client, RelatedContact, Bill,
                                       Activity, BillingSummary
  * backend/app/services/firm_data.py  EmployeeProductivity,
                                       FirmProductivityData,
                                       RevenueByPracticeArea(Data),
                                       TrustManagementData

Logic is byte-for-byte where it matters (aggregation, attribution, bucket
math). The only omissions are the format_currency / format_percent
presentation helpers, which tools do not need: results are plain JSON with
raw numbers.
"""

from datetime import date as date_type, timedelta


# ---------------------------------------------------------------------------
# Matter-level classes (from case.py)
# ---------------------------------------------------------------------------

class Case:
    """Parses a Clio matter JSON response into a structured object."""

    def __init__(self, data):
        self.id = data.get("id")
        self.display_number = data.get("display_number", "")
        self.description = data.get("description", "")
        self.status = data.get("status", "")
        self.open_date = data.get("open_date")
        self.close_date = data.get("close_date")
        self.pending_date = data.get("pending_date")
        self.billable = data.get("billable", False)
        self.billing_method = data.get("billing_method", "")
        self.location = data.get("location", "")
        self.client_reference = data.get("client_reference", "")
        self.created_at = data.get("created_at")
        self.updated_at = data.get("updated_at")

        # Nested objects
        self.client = Client(data["client"]) if data.get("client") else None
        self.practice_area = (data.get("practice_area") or {}).get("name", "")
        self.responsible_attorney = (data.get("responsible_attorney") or {}).get("name", "")
        self.originating_attorney = (data.get("originating_attorney") or {}).get("name", "")
        self.matter_stage = (data.get("matter_stage") or {}).get("name", "")

        # Related contacts (populated separately via set_related_contacts)
        self.opposing_parties = []
        self.opposing_counsel = []
        self.court_contacts = []  # Judge, Clerk of Court, etc.
        self.other_contacts = []

        # Billing data (populated separately via set_billing_data)
        self.bills = []
        self.activities = []
        self.billing_summary = BillingSummary()

    @property
    def title(self):
        return self.display_number or f"Matter #{self.id}"

    def set_related_contacts(self, related_contacts_data):
        """Parse related contacts and categorize by relationship description."""
        for item in related_contacts_data:
            contact = RelatedContact(item)

            # Skip the matter client (already shown in Client section)
            if item.get("is_matter_client"):
                continue

            desc = (contact.relationship_description or "").lower()

            if any(term in desc for term in ["opposing party", "adverse party",
                                             "defendant", "plaintiff",
                                             "respondent", "petitioner"]):
                self.opposing_parties.append(contact)
            elif any(term in desc for term in ["opposing counsel",
                                               "adverse counsel",
                                               "defense counsel",
                                               "defense attorney"]):
                self.opposing_counsel.append(contact)
            elif any(term in desc for term in ["judge", "clerk", "court",
                                               "magistrate", "mediator"]):
                self.court_contacts.append(contact)
            else:
                self.other_contacts.append(contact)

    def set_billing_data(self, bills_data, activities_data):
        """Parse billing and activity data into structured objects."""
        self.bills = [Bill(b) for b in bills_data]
        self.activities = [Activity(a) for a in activities_data]

        total_billed = sum(b.total or 0 for b in self.bills)
        total_paid = sum(b.paid or 0 for b in self.bills)
        total_balance = sum(b.balance or 0 for b in self.bills)
        total_hours = sum(
            a.hours or 0 for a in self.activities if a.type == "TimeEntry"
        )
        billable_hours = sum(
            a.hours or 0
            for a in self.activities
            if a.type == "TimeEntry" and not a.non_billable
        )
        non_billable_hours = sum(
            a.hours or 0
            for a in self.activities
            if a.type == "TimeEntry" and a.non_billable
        )

        self.billing_summary = BillingSummary(
            total_billed=total_billed,
            total_paid=total_paid,
            outstanding_balance=total_balance,
            total_hours=total_hours,
            billable_hours=billable_hours,
            non_billable_hours=non_billable_hours,
            invoice_count=len(self.bills),
            time_entry_count=len(
                [a for a in self.activities if a.type == "TimeEntry"]
            ),
        )


class Client:
    """Parses a Clio client/contact JSON into a structured object."""

    def __init__(self, data):
        self.id = data.get("id")
        self.name = data.get("name", "")
        self.first_name = data.get("first_name", "")
        self.last_name = data.get("last_name", "")
        self.type = data.get("type", "")
        self.email = data.get("primary_email_address", "")
        self.phone = data.get("primary_phone_number", "")


class RelatedContact:
    """A contact linked to a matter via a relationship (opposing party, counsel, etc.)."""

    def __init__(self, data):
        self.id = data.get("id")
        self.name = data.get("name", "")
        self.first_name = data.get("first_name", "")
        self.last_name = data.get("last_name", "")
        self.type = data.get("type", "")
        self.title = data.get("title", "")
        self.prefix = data.get("prefix", "")
        self.email = data.get("primary_email_address", "")
        self.phone = data.get("primary_phone_number", "")
        self.company = (data.get("company") or {}).get("name", "")

        rel = data.get("relationship") or {}
        self.relationship_description = rel.get("description") or ""

        addresses = data.get("addresses") or []
        if addresses:
            addr = addresses[0]
            parts = [
                addr.get("street", ""),
                addr.get("city", ""),
                addr.get("province", ""),
                addr.get("postal_code", ""),
            ]
            self.address = ", ".join(p for p in parts if p)
        else:
            self.address = ""

    @property
    def display_name(self):
        parts = []
        if self.prefix:
            parts.append(self.prefix)
        parts.append(self.name)
        if self.title:
            parts.append(f"({self.title})")
        return " ".join(parts)


class Bill:
    """Parses a Clio bill/invoice JSON into a structured object."""

    def __init__(self, data):
        self.id = data.get("id")
        self.number = data.get("number", "")
        self.issued_at = data.get("issued_at")
        self.due_at = data.get("due_at")
        self.state = data.get("state", "")
        self.total = data.get("total")
        self.sub_total = data.get("sub_total")
        self.balance = data.get("balance")
        self.paid = data.get("paid")
        self.paid_at = data.get("paid_at")
        self.due = data.get("due")
        self.tax_sum = data.get("tax_sum")
        self.subject = data.get("subject", "")

    @property
    def state_display(self):
        states = {
            "draft": "Draft",
            "awaiting_approval": "Awaiting Approval",
            "awaiting_payment": "Awaiting Payment",
            "paid": "Paid",
            "void": "Void",
            "deleted": "Deleted",
        }
        return states.get(self.state, self.state)


class Activity:
    """Parses a Clio activity/time-entry JSON into a structured object."""

    def __init__(self, data):
        self.id = data.get("id")
        self.type = data.get("type", "")
        self.date = data.get("date")
        self.hours = data.get("rounded_quantity_in_hours") or data.get("quantity_in_hours")
        self.price = data.get("price")
        self.total = data.get("total")
        self.note = data.get("note", "")
        self.billed = data.get("billed", False)
        self.on_bill = data.get("on_bill", False)
        self.non_billable = data.get("non_billable", False)
        self.flat_rate = data.get("flat_rate", False)
        self.user_name = (data.get("user") or {}).get("name", "")
        self.description_name = (data.get("activity_description") or {}).get("name", "")

    @property
    def type_display(self):
        types = {
            "TimeEntry": "Time",
            "ExpenseEntry": "Expense",
            "HardCostEntry": "Hard Cost",
            "SoftCostEntry": "Soft Cost",
        }
        return types.get(self.type, self.type)


class BillingSummary:
    """Aggregated billing summary for a matter."""

    def __init__(self, total_billed=0, total_paid=0, outstanding_balance=0,
                 total_hours=0, billable_hours=0, non_billable_hours=0,
                 invoice_count=0, time_entry_count=0):
        self.total_billed = total_billed
        self.total_paid = total_paid
        self.outstanding_balance = outstanding_balance
        self.total_hours = total_hours
        self.billable_hours = billable_hours
        self.non_billable_hours = non_billable_hours
        self.invoice_count = invoice_count
        self.time_entry_count = time_entry_count


# ---------------------------------------------------------------------------
# Firm-wide classes (from firm_data.py)
# ---------------------------------------------------------------------------

def _working_days(start_str, end_str):
    """Count weekdays (Mon-Fri) between two ISO date strings, inclusive."""
    start = date_type.fromisoformat(start_str)
    end = date_type.fromisoformat(end_str)
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


class EmployeeProductivity:
    """Aggregated productivity data for a single employee."""

    def __init__(self, user_id, name, rate=None):
        self.user_id = user_id
        self.name = name
        self.rate = rate
        self.total_hours = 0.0
        self.billable_hours = 0.0
        self.non_billable_hours = 0.0
        self.total_billed_amount = 0.0
        self.collected_revenue = 0.0
        self.write_off_hours = 0.0
        self.write_off_amount = 0.0
        self.target_hours = None  # Set externally based on date range

    @property
    def realization_rate(self):
        """Total Billed Amount / (Billable Hours x Hourly Rate)."""
        if not self.rate or self.billable_hours == 0:
            return None
        potential = self.billable_hours * self.rate
        if potential == 0:
            return None
        return self.total_billed_amount / potential

    @property
    def collection_rate(self):
        """Collected Revenue / Total Billed Amount."""
        if self.total_billed_amount == 0:
            return None
        return self.collected_revenue / self.total_billed_amount

    @property
    def utilization_rate(self):
        """Billable Hours / Target Hours."""
        if not self.target_hours or self.target_hours == 0:
            return None
        return self.billable_hours / self.target_hours


class FirmProductivityData:
    """Aggregated firm-wide productivity data for a date range."""

    def __init__(self, start_date, end_date, users_data, activities_data, bills_data,
                 practice_area_lookup=None):
        self.start_date = start_date
        self._pa_lookup = practice_area_lookup or {}
        self.end_date = end_date

        # Build user lookup from Clio users
        users_by_id = {}
        for u in users_data:
            users_by_id[u["id"]] = {
                "name": u.get("name", ""),
                "rate": u.get("rate"),
            }

        # Aggregate activities by user
        employees = {}
        matter_hours = {}  # matter_id -> {uid -> billable hours}
        for activity in activities_data:
            user_info = activity.get("user") or {}
            uid = user_info.get("id")
            if not uid:
                continue
            if uid not in employees:
                u_data = users_by_id.get(uid, {})
                employees[uid] = EmployeeProductivity(
                    uid,
                    user_info.get("name", u_data.get("name", "Unknown")),
                    rate=u_data.get("rate"),
                )
            emp = employees[uid]
            hours = (
                activity.get("rounded_quantity_in_hours")
                or activity.get("quantity_in_hours")
                or 0
            )
            emp.total_hours += hours
            if activity.get("non_billable"):
                emp.non_billable_hours += hours
            else:
                emp.billable_hours += hours
                emp.total_billed_amount += activity.get("total") or 0

                matter = activity.get("matter") or {}
                mid = matter.get("id")
                if mid:
                    matter_hours.setdefault(mid, {})
                    matter_hours[mid][uid] = matter_hours[mid].get(uid, 0) + hours

            if activity.get("no_charge"):
                emp.write_off_hours += hours
                emp.write_off_amount += hours * (emp.rate or 0)

        # Collected revenue: attribute paid bill amounts to employees based on
        # their share of billable hours on the matters associated with each bill.
        for b in bills_data:
            if b.get("state") != "paid":
                continue
            bill_paid = b.get("paid") or 0
            if bill_paid <= 0:
                continue

            matter_ids = {
                m.get("id")
                for m in (b.get("matters") or [])
                if m.get("id")
            }
            if not matter_ids:
                continue

            user_hours = {}
            for mid in matter_ids:
                for uid, hrs in matter_hours.get(mid, {}).items():
                    user_hours[uid] = user_hours.get(uid, 0) + hrs

            total_hours = sum(user_hours.values())
            if total_hours <= 0:
                continue

            for uid, hrs in user_hours.items():
                share = hrs / total_hours
                if uid in employees:
                    employees[uid].collected_revenue += bill_paid * share

        self.employees = sorted(employees.values(), key=lambda e: e.name)

        # Target hours & utilization
        working_days = _working_days(start_date, end_date)
        default_target = working_days * 8.0
        self.target_hours = default_target
        for emp in self.employees:
            emp.target_hours = default_target

        # Firm totals
        self.total_hours = sum(e.total_hours for e in self.employees)
        self.total_billable_hours = sum(e.billable_hours for e in self.employees)
        self.total_non_billable_hours = sum(e.non_billable_hours for e in self.employees)
        self.total_billed_amount = sum(e.total_billed_amount for e in self.employees)
        self.total_collected_revenue = sum(e.collected_revenue for e in self.employees)
        self.total_write_off_hours = sum(e.write_off_hours for e in self.employees)
        self.total_write_off_amount = sum(e.write_off_amount for e in self.employees)

        # Firm-wide rates
        total_potential = sum(
            (e.billable_hours * e.rate) for e in self.employees if e.rate
        )
        self.firm_realization_rate = (
            self.total_billed_amount / total_potential if total_potential > 0 else None
        )
        self.firm_collection_rate = (
            self.total_collected_revenue / self.total_billed_amount
            if self.total_billed_amount > 0 else None
        )
        self.firm_utilization_rate = (
            self.total_billable_hours / (default_target * len(self.employees))
            if self.employees and default_target > 0 else None
        )

        # Invoice / revenue data
        self.bills = [Bill(b) for b in bills_data]
        self.total_invoiced = sum(b.total or 0 for b in self.bills)
        self.total_paid = sum(b.paid or 0 for b in self.bills)
        self.outstanding_balance = sum(b.balance or 0 for b in self.bills)

        # Invoice aging buckets
        reference_date = date_type.fromisoformat(end_date)
        self.aging_buckets = {
            "current": {"label": "Current (0-30 days)", "total": 0.0, "count": 0},
            "31_60":   {"label": "31-60 Days",          "total": 0.0, "count": 0},
            "61_90":   {"label": "61-90 Days",          "total": 0.0, "count": 0},
            "over_90": {"label": "90+ Days",            "total": 0.0, "count": 0},
        }
        for bill in self.bills:
            if bill.state == "paid" or not bill.balance or bill.balance <= 0:
                continue
            if not bill.issued_at:
                continue
            issued = date_type.fromisoformat(bill.issued_at[:10])
            age_days = (reference_date - issued).days
            if age_days <= 30:
                bucket = "current"
            elif age_days <= 60:
                bucket = "31_60"
            elif age_days <= 90:
                bucket = "61_90"
            else:
                bucket = "over_90"
            self.aging_buckets[bucket]["total"] += bill.balance
            self.aging_buckets[bucket]["count"] += 1

        self.total_outstanding_aging = sum(
            b["total"] for b in self.aging_buckets.values()
        )

        # Revenue by Practice Area
        self.revenue_by_practice_area_collected = RevenueByPracticeArea(
            bills_data, end_date, mode="collected",
            practice_area_lookup=self._pa_lookup,
        )
        self.revenue_by_practice_area_outstanding = RevenueByPracticeArea(
            bills_data, end_date, mode="outstanding",
            practice_area_lookup=self._pa_lookup,
        )

    @property
    def title(self):
        return f"Firm Productivity ({self.start_date} to {self.end_date})"


class RevenueByPracticeArea:
    """Revenue (collected or outstanding) grouped by practice area and AR aging bucket."""

    BUCKET_KEYS = ["1_30", "31_60", "61_90", "91_plus"]
    BUCKET_LABELS = {
        "1_30": "1-30 Days",
        "31_60": "31-60 Days",
        "61_90": "61-90 Days",
        "91_plus": "91+ Days",
    }

    def __init__(self, bills_data, reference_date_str, mode="collected",
                 practice_area_lookup=None):
        self.mode = mode
        self.reference_date = date_type.fromisoformat(reference_date_str)
        pa_lookup = practice_area_lookup or {}

        pa_buckets = {}

        for b in bills_data:
            matters = b.get("matters") or []
            practice_area = "Uncategorized"
            if matters:
                matter = matters[0] if isinstance(matters, list) else matters
                pa_obj = matter.get("practice_area") or {}
                pa_name = pa_obj.get("name")
                if not pa_name and pa_obj.get("id"):
                    pa_name = pa_lookup.get(pa_obj["id"])
                if pa_name:
                    practice_area = pa_name

            if mode == "collected":
                if b.get("state") != "paid":
                    continue
                amount = b.get("paid") or 0
                if amount <= 0:
                    continue
            else:  # outstanding
                if b.get("state") == "paid":
                    continue
                amount = b.get("balance") or 0
                if amount <= 0:
                    continue

            issued_at = b.get("issued_at")
            if not issued_at:
                continue
            issued = date_type.fromisoformat(issued_at[:10])

            if mode == "collected":
                paid_at = b.get("paid_at")
                if not paid_at:
                    continue
                paid_date = date_type.fromisoformat(paid_at[:10])
                age_days = (paid_date - issued).days
            else:
                age_days = (self.reference_date - issued).days

            if age_days <= 30:
                bucket = "1_30"
            elif age_days <= 60:
                bucket = "31_60"
            elif age_days <= 90:
                bucket = "61_90"
            else:
                bucket = "91_plus"

            if practice_area not in pa_buckets:
                pa_buckets[practice_area] = {k: 0.0 for k in self.BUCKET_KEYS}
            pa_buckets[practice_area][bucket] += amount

        self.rows = []
        for pa in sorted(pa_buckets.keys()):
            buckets = pa_buckets[pa]
            row_total = sum(buckets.values())
            self.rows.append({
                "practice_area": pa,
                **buckets,
                "total": row_total,
            })

        self.column_totals = {k: 0.0 for k in self.BUCKET_KEYS}
        self.column_totals["total"] = 0.0
        for row in self.rows:
            for k in self.BUCKET_KEYS:
                self.column_totals[k] += row[k]
            self.column_totals["total"] += row["total"]

    @property
    def title(self):
        if self.mode == "collected":
            return "Collected Revenue by Practice Area"
        return "Outstanding AR by Practice Area"

    @property
    def mode_label(self):
        return "Collected Revenue" if self.mode == "collected" else "Outstanding Balance"


class RevenueByPracticeAreaData:
    """Standalone data model for the Revenue by Practice Area report."""

    def __init__(self, start_date, end_date, bills_data, mode="collected",
                 practice_area_lookup=None):
        self.start_date = start_date
        self.end_date = end_date
        self.mode = mode
        self.revenue = RevenueByPracticeArea(
            bills_data, end_date, mode=mode,
            practice_area_lookup=practice_area_lookup,
        )

    @property
    def title(self):
        label = "Collected Revenue" if self.mode == "collected" else "Outstanding AR"
        return f"{label} by Practice Area ({self.start_date} to {self.end_date})"


class TrustManagementData:
    """Data model for the Trust Management Report.

    Identifies clients/matters whose trust balances are below the required
    threshold. The "Initial Trust Deposit" custom field is the minimum
    threshold for all matters; "Trust Commitment Program" is informational.
    """

    TCP_FIELD_NAME = "trust commitment program"
    INITIAL_DEPOSIT_FIELD_NAME = "initial trust deposit"

    def __init__(self, matters_data):
        self.rows = []
        self.total_deficit = 0.0
        self.total_clients_below = 0
        self.tcp_count = 0
        self.non_tcp_count = 0

        client_data = {}  # client_name -> {trust_balance, threshold, is_tcp}

        for matter in matters_data:
            client = matter.get("client") or {}
            client_name = client.get("name") or "Unknown Client"

            custom_fields = matter.get("custom_field_values") or []
            is_tcp = False
            initial_deposit = None

            for cf in custom_fields:
                field_name = (cf.get("field_name") or "").strip().lower()
                value = cf.get("value")

                if field_name == self.TCP_FIELD_NAME:
                    if isinstance(value, bool):
                        is_tcp = value
                    elif isinstance(value, str):
                        is_tcp = value.lower() in ("true", "yes", "1", "on")
                    else:
                        is_tcp = bool(value)

                elif field_name == self.INITIAL_DEPOSIT_FIELD_NAME:
                    try:
                        initial_deposit = float(value) if value else None
                    except (ValueError, TypeError):
                        initial_deposit = None

            account_balances = matter.get("account_balances") or []
            trust_balance = self._extract_trust_balance(account_balances)

            threshold = initial_deposit

            if threshold is None or threshold <= 0:
                continue
            if trust_balance is None:
                trust_balance = 0.0

            matter_deficit = max(0, threshold - trust_balance)

            if client_name not in client_data:
                client_data[client_name] = {
                    "amount_in_trust": 0.0,
                    "min_threshold": 0.0,
                    "amount_below": 0.0,
                    "is_tcp": False,
                }
            client_data[client_name]["amount_in_trust"] += trust_balance
            client_data[client_name]["min_threshold"] += threshold
            client_data[client_name]["amount_below"] += matter_deficit
            if is_tcp:
                client_data[client_name]["is_tcp"] = True

        for client_name, data in client_data.items():
            if data["amount_below"] <= 0:
                continue

            self.rows.append({
                "client_name": client_name,
                "amount_in_trust": data["amount_in_trust"],
                "min_threshold": data["min_threshold"],
                "amount_below": data["amount_below"],
                "is_tcp": data["is_tcp"],
            })
            self.total_deficit += data["amount_below"]
            self.total_clients_below += 1
            if data["is_tcp"]:
                self.tcp_count += 1
            else:
                self.non_tcp_count += 1

        self.rows.sort(key=lambda r: r["amount_below"], reverse=True)

    def _extract_trust_balance(self, account_balances):
        if not account_balances:
            return None

        if isinstance(account_balances, list):
            for acct in account_balances:
                if isinstance(acct, dict) and acct.get("redacted"):
                    continue
                acct_type = (acct.get("type") or "").lower()
                if acct_type == "trust":
                    return self._parse_amount(acct.get("balance"))
            return None

        if isinstance(account_balances, dict):
            if account_balances.get("type", "").lower() == "trust":
                return self._parse_amount(account_balances.get("balance"))

        return None

    @staticmethod
    def _parse_amount(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @property
    def title(self):
        return "Trust Management Report"
