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

            # Skip the matter client — already shown in Client section
            if item.get("is_matter_client"):
                continue

            desc = contact.relationship_description.lower()

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

        # Compute billing summary
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

        # Relationship info
        rel = data.get("relationship") or {}
        self.relationship_description = rel.get("description", "")

        # Full address (first one if available)
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
        """Name with prefix and title if available."""
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
        """Human-readable state label."""
        states = {
            "draft": "Draft",
            "awaiting_approval": "Awaiting Approval",
            "awaiting_payment": "Awaiting Payment",
            "paid": "Paid",
            "void": "Void",
            "deleted": "Deleted",
        }
        return states.get(self.state, self.state)

    def format_currency(self, amount):
        """Format a number as USD currency."""
        if amount is None:
            return "—"
        return f"${amount:,.2f}"


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

    def format_currency(self, amount):
        if amount is None:
            return "—"
        return f"${amount:,.2f}"
