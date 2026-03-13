"""Data models for firm-wide reports (not tied to individual cases)."""

from app.services.case import Bill


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

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"


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

        # Build set of paid bill IDs for collected-revenue calculation
        paid_bill_ids = set()
        for b in bills_data:
            if b.get("state") == "paid":
                paid_bill_ids.add(b.get("id"))

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

            # Collected revenue: activity total when its bill has been paid
            bill_info = activity.get("bill") or {}
            bill_id = bill_info.get("id")
            if bill_id and bill_id in paid_bill_ids:
                emp.collected_revenue += activity.get("total") or 0

        self.employees = sorted(employees.values(), key=lambda e: e.name)

        # Firm totals
        self.total_hours = sum(e.total_hours for e in self.employees)
        self.total_billable_hours = sum(e.billable_hours for e in self.employees)
        self.total_non_billable_hours = sum(e.non_billable_hours for e in self.employees)
        self.total_billed_amount = sum(e.total_billed_amount for e in self.employees)
        self.total_collected_revenue = sum(e.collected_revenue for e in self.employees)

        # Invoice / revenue data (reuse existing Bill class)
        self.bills = [Bill(b) for b in bills_data]
        self.total_invoiced = sum(b.total or 0 for b in self.bills)
        self.total_paid = sum(b.paid or 0 for b in self.bills)
        self.outstanding_balance = sum(b.balance or 0 for b in self.bills)

    @property
    def title(self):
        return f"Firm Productivity ({self.start_date} to {self.end_date})"

    def format_currency(self, amount):
        if amount is None:
            return "\u2014"
        return f"${amount:,.2f}"
