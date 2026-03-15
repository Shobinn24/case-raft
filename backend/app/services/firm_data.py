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

    def __init__(self, start_date, end_date, users_data, activities_data, bills_data):
        self.start_date = start_date
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

            # Write-off tracking: no_charge activities
            if activity.get("no_charge"):
                emp.write_off_hours += hours
                emp.write_off_amount += hours * (emp.rate or 0)

        # Collected revenue: calculated from paid bills' line items.
        # For each paid bill, look at its line items to find which users
        # contributed work, then attribute the bill's paid amount
        # proportionally based on each user's share of line item totals.
        for b in bills_data:
            if b.get("state") != "paid":
                continue
            bill_paid = b.get("paid") or 0
            if bill_paid <= 0:
                continue

            # Sum line item totals per user on this bill
            user_totals = {}  # uid -> sum of line item totals
            line_items = b.get("line_items") or []
            bill_line_total = 0.0
            for li in line_items:
                li_total = li.get("total") or 0
                activity = li.get("activity") or {}
                user = activity.get("user") or {}
                uid = user.get("id")
                if uid:
                    user_totals[uid] = user_totals.get(uid, 0) + li_total
                    bill_line_total += li_total

            if bill_line_total <= 0:
                continue

            # Distribute the bill's paid amount proportionally by user share
            for uid, user_li_total in user_totals.items():
                share = user_li_total / bill_line_total
                collected = bill_paid * share
                if uid in employees:
                    employees[uid].collected_revenue += collected
                else:
                    # User might not have activities in the date range but
                    # has collected revenue from a bill issued in the range
                    u_data = users_by_id.get(uid, {})
                    emp = EmployeeProductivity(
                        uid,
                        user.get("name", u_data.get("name", "Unknown")),
                        rate=u_data.get("rate"),
                    )
                    emp.collected_revenue += collected
                    employees[uid] = emp

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
