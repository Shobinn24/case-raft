"""Data models for firm-wide reports (not tied to individual cases)."""

from datetime import date as date_type, timedelta

from app.services.case import Bill


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

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"

    def format_percent(self, value):
        if value is None:
            return "\u2014"
        return f"{value * 100:.1f}%"


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
        # Also build matter_hours: {matter_id: {uid: hours}} for bill attribution
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

                # Track billable hours per matter for collected revenue attribution
                matter = activity.get("matter") or {}
                mid = matter.get("id")
                if mid:
                    matter_hours.setdefault(mid, {})
                    matter_hours[mid][uid] = matter_hours[mid].get(uid, 0) + hours

            # Write-off tracking: no_charge activities
            if activity.get("no_charge"):
                emp.write_off_hours += hours
                emp.write_off_amount += hours * (emp.rate or 0)

        # Collected revenue: attribute paid bill amounts to employees based on
        # their share of billable hours on the matters associated with each bill.
        # (Clio's bills endpoint does not expose line_items directly.)
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

            # Sum billable hours per user across all matters on this bill
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

        # Invoice / revenue data (reuse existing Bill class)
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

        # Revenue by Practice Area (for embeddable section in firm report)
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

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"

    def format_percent(self, value):
        if value is None:
            return "\u2014"
        return f"{value * 100:.1f}%"


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
        """
        Args:
            bills_data: raw bill dicts from Clio API (with matters nested).
            reference_date_str: ISO date string used as the aging reference point.
            mode: "collected" for paid revenue, "outstanding" for unpaid AR.
            practice_area_lookup: dict mapping practice_area id -> name.
                Needed because practice_area is a second-level nest on
                bills->matters and Clio only returns default fields (id).
        """
        self.mode = mode
        self.reference_date = date_type.fromisoformat(reference_date_str)
        pa_lookup = practice_area_lookup or {}

        # practice_area -> {bucket_key -> amount}
        pa_buckets = {}

        for b in bills_data:
            # Determine practice area from the nested matter
            matters = b.get("matters") or []
            practice_area = "Uncategorized"
            if matters:
                matter = matters[0] if isinstance(matters, list) else matters
                pa_obj = matter.get("practice_area") or {}
                # Try name first (if Clio returns it), else use id lookup
                pa_name = pa_obj.get("name")
                if not pa_name and pa_obj.get("id"):
                    pa_name = pa_lookup.get(pa_obj["id"])
                if pa_name:
                    practice_area = pa_name

            # Filter based on mode
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

            # Calculate age for bucket placement
            issued_at = b.get("issued_at")
            if not issued_at:
                continue
            issued = date_type.fromisoformat(issued_at[:10])

            if mode == "collected":
                # For collected revenue: age = how long the bill was
                # outstanding before being paid (paid_at - issued_at)
                paid_at = b.get("paid_at")
                if not paid_at:
                    continue
                paid_date = date_type.fromisoformat(paid_at[:10])
                age_days = (paid_date - issued).days
            else:
                # For outstanding AR: age = how old the unpaid bill is
                # from the reference date (end of report period)
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

        # Build sorted rows
        self.rows = []
        for pa in sorted(pa_buckets.keys()):
            buckets = pa_buckets[pa]
            row_total = sum(buckets.values())
            self.rows.append({
                "practice_area": pa,
                **buckets,
                "total": row_total,
            })

        # Column totals
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

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"


class TrustManagementData:
    """Data model for the Trust Management Report.

    Identifies clients/matters whose trust balances are below the required
    threshold. The "Initial Trust Deposit" custom field is used as the
    minimum threshold for all matters (both TCP and non-TCP).

    The "Trust Commitment Program" custom field is informational — it shows
    whether the client is in TCP in the report, but both use the same
    threshold field since Clio's API does not expose the evergreen retainer
    threshold amount.

    Clio API field structures (confirmed via debug endpoint):
    - account_balances: list of dicts with keys {id, balance, currency_id, name, type}
      where type is "Operating" or "Trust"
    - evergreen_retainer: only has {id, created_at, updated_at} — no threshold amount
    - custom_field_values: list of dicts with {id, field_name, value}
    """

    # Custom field names in Clio (case-insensitive matching)
    TCP_FIELD_NAME = "trust commitment program"
    INITIAL_DEPOSIT_FIELD_NAME = "initial trust deposit"

    def __init__(self, matters_data):
        self.rows = []
        self.total_deficit = 0.0
        self.total_clients_below = 0
        self.tcp_count = 0
        self.non_tcp_count = 0

        # Aggregate at the client level: group all matters by client name,
        # sum trust balances, sum thresholds, and compute deficit per client.
        client_data = {}  # client_name -> {trust_balance, threshold, is_tcp}

        for matter in matters_data:
            client = matter.get("client") or {}
            client_name = client.get("name") or "Unknown Client"

            # --- Extract custom field values ---
            custom_fields = matter.get("custom_field_values") or []
            is_tcp = False
            initial_deposit = None

            for cf in custom_fields:
                field_name = (cf.get("field_name") or "").strip().lower()
                value = cf.get("value")

                if field_name == self.TCP_FIELD_NAME:
                    # Checkbox custom fields: value can be True/False, "Yes"/"No", etc.
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

            # --- Extract trust balance ---
            account_balances = matter.get("account_balances") or []
            trust_balance = self._extract_trust_balance(account_balances)

            # --- Determine threshold ---
            threshold = initial_deposit

            # Skip matters with no threshold
            if threshold is None or threshold <= 0:
                continue
            if trust_balance is None:
                trust_balance = 0.0

            # Calculate per-matter deficit (only count positive deficits)
            matter_deficit = max(0, threshold - trust_balance)

            # Accumulate into client-level data
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
            # If any matter for this client is in TCP, mark client as TCP
            if is_tcp:
                client_data[client_name]["is_tcp"] = True

        # Build rows — only include clients with a deficit > 0
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

        # Sort by largest deficit first
        self.rows.sort(key=lambda r: r["amount_below"], reverse=True)

    def _extract_trust_balance(self, account_balances):
        """Extract the trust account balance from the account_balances list.

        Confirmed Clio structure:
        [{"id": 123, "balance": 0, "currency_id": null, "name": "1234567", "type": "Operating"}]
        We look for type == "Trust".
        """
        if not account_balances:
            return None

        if isinstance(account_balances, list):
            for acct in account_balances:
                if isinstance(acct, dict) and acct.get("redacted"):
                    continue  # Skip redacted entries
                acct_type = (acct.get("type") or "").lower()
                if acct_type == "trust":
                    return self._parse_amount(acct.get("balance"))
            # No trust-type account found on this matter
            return None

        # Fallback: if it's somehow a dict (shouldn't be based on discovery)
        if isinstance(account_balances, dict):
            if account_balances.get("type", "").lower() == "trust":
                return self._parse_amount(account_balances.get("balance"))

        return None

    @staticmethod
    def _parse_amount(val):
        """Safely parse a numeric amount from various formats."""
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @property
    def title(self):
        return "Trust Management Report"

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"


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

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"
