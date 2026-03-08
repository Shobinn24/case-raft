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

    @property
    def title(self):
        return self.display_number or f"Matter #{self.id}"


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
