"""Mock Clio API responses for local development without an active Clio subscription."""

DEV_MOCK_TOKEN = "dev-mock-token"


def get_mock_matters():
    """Return a list of sample matters for the cases page."""
    return {
        "data": [
            {
                "id": 9001,
                "display_number": "2026-001",
                "description": "Williams v. Metro Transit Authority",
                "status": "open",
                "open_date": "2025-09-15",
                "close_date": None,
                "pending_date": None,
                "client": {"id": 101, "name": "Sarah Williams"},
                "practice_area": {"name": "Personal Injury"},
                "responsible_attorney": {"name": "Shobin Clark"},
                "matter_stage": {"name": "Discovery"},
                "billable": True,
                "billing_method": "hourly",
            },
            {
                "id": 9002,
                "display_number": "2026-002",
                "description": "Greenfield LLC Formation",
                "status": "open",
                "open_date": "2026-01-10",
                "close_date": None,
                "pending_date": None,
                "client": {"id": 102, "name": "Greenfield Enterprises"},
                "practice_area": {"name": "Corporate"},
                "responsible_attorney": {"name": "Shobin Clark"},
                "matter_stage": {"name": "Active"},
                "billable": True,
                "billing_method": "flat",
            },
            {
                "id": 9003,
                "display_number": "2026-003",
                "description": "Nguyen Family Trust Administration",
                "status": "open",
                "open_date": "2025-11-01",
                "close_date": None,
                "pending_date": None,
                "client": {"id": 103, "name": "David Nguyen"},
                "practice_area": {"name": "Estate Planning"},
                "responsible_attorney": {"name": "Shobin Clark"},
                "matter_stage": {"name": "Active"},
                "billable": True,
                "billing_method": "hourly",
            },
            {
                "id": 9004,
                "display_number": "2025-047",
                "description": "Acme Corp v. Beta Industries - Patent Dispute",
                "status": "open",
                "open_date": "2025-06-20",
                "close_date": None,
                "pending_date": None,
                "client": {"id": 104, "name": "Acme Corp"},
                "practice_area": {"name": "Intellectual Property"},
                "responsible_attorney": {"name": "Shobin Clark"},
                "matter_stage": {"name": "Litigation"},
                "billable": True,
                "billing_method": "hourly",
            },
            {
                "id": 9005,
                "display_number": "2026-004",
                "description": "Rivera Employment Discrimination Claim",
                "status": "open",
                "open_date": "2026-02-01",
                "close_date": None,
                "pending_date": None,
                "client": {"id": 105, "name": "Maria Rivera"},
                "practice_area": {"name": "Employment Law"},
                "responsible_attorney": {"name": "Shobin Clark"},
                "matter_stage": {"name": "Pre-Litigation"},
                "billable": True,
                "billing_method": "hourly",
            },
        ]
    }


def get_mock_matter(matter_id):
    """Return a single matter with full details."""
    matters = {m["id"]: m for m in get_mock_matters()["data"]}
    matter = matters.get(matter_id)
    if not matter:
        matter = get_mock_matters()["data"][0]
    # Enrich with extra fields for the detail view
    enriched = {
        **matter,
        "client": {
            **matter["client"],
            "first_name": matter["client"]["name"].split()[0],
            "last_name": matter["client"]["name"].split()[-1],
            "type": "Person",
            "primary_email_address": "client@example.com",
            "primary_phone_number": "(555) 123-4567",
        },
        "originating_attorney": {"name": "Shobin Clark"},
        "location": None,
        "client_reference": None,
        "created_at": matter.get("open_date", "2025-01-01"),
        "updated_at": "2026-03-01",
    }
    return {"data": enriched}


def get_mock_matters_with_trust_data():
    """Return mock matters with trust balances and custom fields for the Trust Report."""
    return [
        # Client 1: Large deficit, TCP enrolled
        {
            "id": 9001,
            "display_number": "2026-001",
            "description": "Williams v. Metro Transit Authority",
            "status": "open",
            "client": {"id": 101, "name": "Sarah Williams"},
            "account_balances": [
                {"id": 1, "balance": 1250.00, "name": "Trust-001", "type": "Trust"},
                {"id": 2, "balance": 5400.00, "name": "Operating-001", "type": "Operating"},
            ],
            "evergreen_retainer": {"id": 1, "created_at": "2025-09-15", "updated_at": "2026-01-01"},
            "custom_field_values": [
                {"id": 1, "field_name": "Trust Commitment Program", "value": True},
                {"id": 2, "field_name": "Initial Trust Deposit", "value": "10000"},
            ],
        },
        # Client 2: Medium deficit, not TCP
        {
            "id": 9002,
            "display_number": "2026-002",
            "description": "Greenfield LLC Formation",
            "status": "open",
            "client": {"id": 102, "name": "Greenfield Enterprises"},
            "account_balances": [
                {"id": 3, "balance": 750.00, "name": "Trust-002", "type": "Trust"},
            ],
            "evergreen_retainer": None,
            "custom_field_values": [
                {"id": 3, "field_name": "Trust Commitment Program", "value": False},
                {"id": 4, "field_name": "Initial Trust Deposit", "value": "3000"},
            ],
        },
        # Client 3: Small deficit, TCP enrolled
        {
            "id": 9003,
            "display_number": "2026-003",
            "description": "Nguyen Family Trust Administration",
            "status": "open",
            "client": {"id": 103, "name": "David Nguyen"},
            "account_balances": [
                {"id": 5, "balance": 4800.00, "name": "Trust-003", "type": "Trust"},
            ],
            "evergreen_retainer": {"id": 2, "created_at": "2025-11-01", "updated_at": "2026-02-15"},
            "custom_field_values": [
                {"id": 5, "field_name": "Trust Commitment Program", "value": True},
                {"id": 6, "field_name": "Initial Trust Deposit", "value": "5000"},
            ],
        },
        # Client 4: Large deficit, TCP enrolled (multiple matters)
        {
            "id": 9004,
            "display_number": "2025-047",
            "description": "Acme Corp v. Beta Industries - Patent Dispute",
            "status": "open",
            "client": {"id": 104, "name": "Acme Corp"},
            "account_balances": [
                {"id": 7, "balance": 2100.00, "name": "Trust-004", "type": "Trust"},
            ],
            "evergreen_retainer": {"id": 3, "created_at": "2025-06-20", "updated_at": "2026-03-01"},
            "custom_field_values": [
                {"id": 7, "field_name": "Trust Commitment Program", "value": True},
                {"id": 8, "field_name": "Initial Trust Deposit", "value": "15000"},
            ],
        },
        # Client 5: Above threshold (should NOT appear in report)
        {
            "id": 9005,
            "display_number": "2026-004",
            "description": "Rivera Employment Discrimination Claim",
            "status": "open",
            "client": {"id": 105, "name": "Maria Rivera"},
            "account_balances": [
                {"id": 9, "balance": 6000.00, "name": "Trust-005", "type": "Trust"},
            ],
            "evergreen_retainer": None,
            "custom_field_values": [
                {"id": 9, "field_name": "Trust Commitment Program", "value": False},
                {"id": 10, "field_name": "Initial Trust Deposit", "value": "5000"},
            ],
        },
    ]


def get_mock_related_contacts(matter_id):
    """Return mock related contacts for a matter."""
    return {
        "data": [
            {
                "id": 201,
                "name": "John Doe",
                "first_name": "John",
                "last_name": "Doe",
                "type": "Person",
                "title": "Attorney",
                "prefix": None,
                "primary_email_address": "jdoe@lawfirm.com",
                "primary_phone_number": "(555) 987-6543",
                "is_matter_client": False,
                "email_addresses": [{"address": "jdoe@lawfirm.com", "name": "Work"}],
                "phone_numbers": [{"number": "(555) 987-6543", "name": "Work"}],
                "addresses": [{"street": "100 Main St", "city": "Boston", "province": "MA", "postal_code": "02101", "country": "US", "name": "Work"}],
                "company": {"name": "Doe & Associates"},
                "relationship": {"id": 1, "description": "Opposing Counsel"},
            },
        ]
    }


def get_mock_activities(matter_id):
    """Return mock time entries for a matter."""
    return {
        "data": [
            {
                "id": 301,
                "type": "TimeEntry",
                "date": "2026-03-20",
                "quantity_in_hours": 2.5,
                "rounded_quantity_in_hours": 2.5,
                "price": 350.00,
                "total": 875.00,
                "note": "Research and draft motion to compel",
                "flat_rate": False,
                "billed": True,
                "on_bill": True,
                "non_billable": False,
                "non_billable_total": 0,
                "no_charge": False,
                "user": {"name": "Shobin Clark"},
                "activity_description": {"name": "Research"},
                "matter": {"id": matter_id},
            },
            {
                "id": 302,
                "type": "TimeEntry",
                "date": "2026-03-18",
                "quantity_in_hours": 1.0,
                "rounded_quantity_in_hours": 1.0,
                "price": 350.00,
                "total": 350.00,
                "note": "Client phone call regarding case status",
                "flat_rate": False,
                "billed": False,
                "on_bill": False,
                "non_billable": False,
                "non_billable_total": 0,
                "no_charge": False,
                "user": {"name": "Shobin Clark"},
                "activity_description": {"name": "Communication"},
                "matter": {"id": matter_id},
            },
        ]
    }


def get_mock_bills(matter_id):
    """Return mock bills for a matter."""
    return {
        "data": [
            {
                "id": 401,
                "number": "INV-2026-001",
                "issued_at": "2026-03-01",
                "due_at": "2026-03-31",
                "state": "awaiting_payment",
                "total": 3500.00,
                "sub_total": 3500.00,
                "balance": 3500.00,
                "paid": 0,
                "paid_at": None,
                "tax_sum": 0,
                "total_tax": 0,
                "start_at": "2026-02-01",
                "end_at": "2026-02-28",
                "subject": "February 2026 Legal Services",
                "type": "MatterBill",
            },
        ]
    }


def get_mock_contact(contact_id):
    """Stub contact for the dev mock layer. Matches the shape returned by
    ClioAPIClient.get_contact so any code path that expects a contact dict
    can be exercised against the mock.
    """
    return {
        "data": {
            "id": contact_id,
            "name": "Mock Contact",
            "first_name": "Mock",
            "middle_name": None,
            "last_name": "Contact",
            "type": "Person",
            "title": None,
            "prefix": None,
            "date_of_birth": None,
            "primary_email_address": "mock.contact@example.com",
            "secondary_email_address": None,
            "primary_phone_number": "+1-555-555-0100",
            "secondary_phone_number": None,
            "addresses": [],
            "email_addresses": [
                {"address": "mock.contact@example.com", "name": "Work"}
            ],
            "phone_numbers": [
                {"number": "+1-555-555-0100", "name": "Work"}
            ],
            "company": None,
            "is_client": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    }
