"""Realistic Clio v4 response shapes for tool tests, mirrored from
backend/app/services/mock_clio_data.py (with additions for tasks, calendar
entries, contacts search, and firm-wide productivity data)."""


def matters_list(count=5):
    base = [
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
    rows = []
    i = 0
    while len(rows) < count:
        template = base[i % len(base)]
        row = dict(template)
        if i >= len(base):
            row = {**template, "id": template["id"] + 1000 * (i // len(base)),
                   "display_number": f"{template['display_number']}-{i}"}
        rows.append(row)
        i += 1
    return {"data": rows}


def matter_detail(matter_id=9001):
    return {
        "data": {
            "id": matter_id,
            "display_number": "2026-001",
            "description": "Williams v. Metro Transit Authority",
            "status": "open",
            "open_date": "2025-09-15",
            "close_date": None,
            "pending_date": None,
            "client": {
                "id": 101,
                "name": "Sarah Williams",
                "first_name": "Sarah",
                "last_name": "Williams",
                "type": "Person",
                "primary_email_address": "sarah@example.com",
                "primary_phone_number": "(555) 123-4567",
            },
            "practice_area": {"name": "Personal Injury"},
            "responsible_attorney": {"name": "Shobin Clark"},
            "originating_attorney": {"name": "Shobin Clark"},
            "matter_stage": {"name": "Discovery"},
            "billable": True,
            "billing_method": "hourly",
            "location": None,
            "client_reference": None,
            "created_at": "2025-09-15",
            "updated_at": "2026-03-01",
        }
    }


def related_contacts():
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
                "company": {"name": "Doe & Associates"},
                "relationship": {"id": 1, "description": "Opposing Counsel"},
            },
            {
                "id": 202,
                "name": "Metro Transit Authority",
                "type": "Company",
                "is_matter_client": False,
                "relationship": {"id": 2, "description": "Opposing Party"},
            },
            {
                "id": 203,
                "name": "Hon. Rachel Kim",
                "type": "Person",
                "is_matter_client": False,
                "relationship": {"id": 3, "description": "Judge"},
            },
            {
                "id": 101,
                "name": "Sarah Williams",
                "type": "Person",
                "is_matter_client": True,
                "relationship": {"id": 4, "description": "Client"},
            },
        ]
    }


def matter_activities(matter_id=9001):
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
                "billed": True,
                "non_billable": False,
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
                "billed": False,
                "non_billable": True,
                "no_charge": False,
                "user": {"name": "Shobin Clark"},
                "activity_description": {"name": "Communication"},
                "matter": {"id": matter_id},
            },
        ]
    }


def matter_bills():
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
                "balance": 2000.00,
                "paid": 1500.00,
                "paid_at": None,
                "subject": "February 2026 Legal Services",
            },
        ]
    }


def contacts_search():
    return {
        "data": [
            {
                "id": 101,
                "name": "Sarah Williams",
                "first_name": "Sarah",
                "last_name": "Williams",
                "type": "Person",
                "primary_email_address": "sarah@example.com",
                "primary_phone_number": "(555) 123-4567",
                "company": None,
                "is_client": True,
            },
            {
                "id": 106,
                "name": "Sarah Chen",
                "type": "Person",
                "primary_email_address": "schen@example.com",
                "primary_phone_number": "(555) 222-3333",
                "company": {"name": "Chen Consulting"},
                "is_client": False,
            },
            {
                "id": 107,
                "name": "Sarah Lopez",
                "type": "Person",
                "primary_email_address": "slopez@example.com",
                "primary_phone_number": None,
                "company": None,
                "is_client": False,
            },
        ]
    }


def contact_detail(contact_id=101):
    return {
        "data": {
            "id": contact_id,
            "name": "Sarah Williams",
            "first_name": "Sarah",
            "last_name": "Williams",
            "type": "Person",
            "title": None,
            "is_client": True,
            "primary_email_address": "sarah@example.com",
            "primary_phone_number": "(555) 123-4567",
            "email_addresses": [{"address": "sarah@example.com", "name": "Work"}],
            "phone_numbers": [{"number": "(555) 123-4567", "name": "Mobile"}],
            "addresses": [{"street": "12 Elm St", "city": "Boston",
                           "province": "MA", "postal_code": "02101",
                           "country": "US", "name": "Home"}],
            "company": None,
            "created_at": "2025-09-15T00:00:00Z",
            "updated_at": "2026-03-01T00:00:00Z",
        }
    }


def firm_users():
    return {
        "data": [
            {"id": 1, "name": "Shobin Clark", "rate": 350.0, "enabled": True},
            {"id": 2, "name": "Ana Torres", "rate": 250.0, "enabled": True},
        ]
    }


def firm_activities():
    """Time entries for 2026-06-01 .. 2026-06-30 (working days: 22).

    Shobin: 10h billable ($3500) on matter 9001, 2h non-billable.
    Ana:     8h billable ($2000) on matter 9002, 1h no-charge billable ($0
             total but write-off tracked).
    """
    return [
        {
            "id": 501, "type": "TimeEntry", "date": "2026-06-05",
            "quantity_in_hours": 10.0, "rounded_quantity_in_hours": 10.0,
            "total": 3500.0, "non_billable": False, "no_charge": False,
            "user": {"id": 1, "name": "Shobin Clark"},
            "matter": {"id": 9001, "display_number": "2026-001"},
        },
        {
            "id": 502, "type": "TimeEntry", "date": "2026-06-10",
            "quantity_in_hours": 2.0, "rounded_quantity_in_hours": 2.0,
            "total": 0.0, "non_billable": True, "no_charge": False,
            "user": {"id": 1, "name": "Shobin Clark"},
            "matter": {"id": 9001, "display_number": "2026-001"},
        },
        {
            "id": 503, "type": "TimeEntry", "date": "2026-06-12",
            "quantity_in_hours": 8.0, "rounded_quantity_in_hours": 8.0,
            "total": 2000.0, "non_billable": False, "no_charge": False,
            "user": {"id": 2, "name": "Ana Torres"},
            "matter": {"id": 9002, "display_number": "2026-002"},
        },
        {
            "id": 504, "type": "TimeEntry", "date": "2026-06-15",
            "quantity_in_hours": 1.0, "rounded_quantity_in_hours": 1.0,
            "total": 0.0, "non_billable": False, "no_charge": True,
            "user": {"id": 2, "name": "Ana Torres"},
            "matter": {"id": 9002, "display_number": "2026-002"},
        },
    ]


def firm_bills():
    """Bills for the June 2026 productivity window.

    One paid bill on matter 9001 (Shobin gets all attribution), one unpaid
    45-day-old bill on matter 9002, one unpaid 10-day-old bill on 9001.
    """
    return [
        {
            "id": 601, "number": "INV-100", "issued_at": "2026-06-02",
            "due_at": "2026-06-30", "state": "paid",
            "total": 3500.0, "balance": 0.0, "paid": 3500.0,
            "paid_at": "2026-06-20",
            "matters": [{"id": 9001, "display_number": "2026-001",
                         "practice_area": {"id": 71, "name": None}}],
        },
        {
            "id": 602, "number": "INV-101", "issued_at": "2026-05-16",
            "due_at": "2026-06-15", "state": "awaiting_payment",
            "total": 2400.0, "balance": 2400.0, "paid": 0.0, "paid_at": None,
            "matters": [{"id": 9002, "display_number": "2026-002",
                         "practice_area": {"id": 72, "name": None}}],
        },
        {
            "id": 603, "number": "INV-102", "issued_at": "2026-06-20",
            "due_at": "2026-07-20", "state": "awaiting_payment",
            "total": 1200.0, "balance": 1200.0, "paid": 0.0, "paid_at": None,
            "matters": [{"id": 9001, "display_number": "2026-001",
                         "practice_area": {"id": 71, "name": None}}],
        },
    ]


def practice_areas():
    return {
        "data": [
            {"id": 71, "name": "Personal Injury"},
            {"id": 72, "name": "Corporate"},
        ]
    }


def trust_matters():
    """Mirrors get_mock_matters_with_trust_data() from the Flask mock layer.

    Expected result: 4 clients below threshold, total deficit 24100.00,
    3 TCP, 1 non-TCP; Rivera (client 5) above threshold and excluded.
    """
    return [
        {
            "id": 9001, "display_number": "2026-001", "status": "open",
            "client": {"id": 101, "name": "Sarah Williams"},
            "account_balances": [
                {"id": 1, "balance": 1250.00, "name": "Trust-001", "type": "Trust"},
                {"id": 2, "balance": 5400.00, "name": "Op-001", "type": "Operating"},
            ],
            "custom_field_values": [
                {"id": 1, "field_name": "Trust Commitment Program", "value": True},
                {"id": 2, "field_name": "Initial Trust Deposit", "value": "10000"},
            ],
        },
        {
            "id": 9002, "display_number": "2026-002", "status": "open",
            "client": {"id": 102, "name": "Greenfield Enterprises"},
            "account_balances": [
                {"id": 3, "balance": 750.00, "name": "Trust-002", "type": "Trust"},
            ],
            "custom_field_values": [
                {"id": 3, "field_name": "Trust Commitment Program", "value": False},
                {"id": 4, "field_name": "Initial Trust Deposit", "value": "3000"},
            ],
        },
        {
            "id": 9003, "display_number": "2026-003", "status": "open",
            "client": {"id": 103, "name": "David Nguyen"},
            "account_balances": [
                {"id": 5, "balance": 4800.00, "name": "Trust-003", "type": "Trust"},
            ],
            "custom_field_values": [
                {"id": 5, "field_name": "Trust Commitment Program", "value": True},
                {"id": 6, "field_name": "Initial Trust Deposit", "value": "5000"},
            ],
        },
        {
            "id": 9004, "display_number": "2025-047", "status": "open",
            "client": {"id": 104, "name": "Acme Corp"},
            "account_balances": [
                {"id": 7, "balance": 2100.00, "name": "Trust-004", "type": "Trust"},
            ],
            "custom_field_values": [
                {"id": 7, "field_name": "Trust Commitment Program", "value": True},
                {"id": 8, "field_name": "Initial Trust Deposit", "value": "15000"},
            ],
        },
        {
            "id": 9005, "display_number": "2026-004", "status": "open",
            "client": {"id": 105, "name": "Maria Rivera"},
            "account_balances": [
                {"id": 9, "balance": 6000.00, "name": "Trust-005", "type": "Trust"},
            ],
            "custom_field_values": [
                {"id": 9, "field_name": "Trust Commitment Program", "value": False},
                {"id": 10, "field_name": "Initial Trust Deposit", "value": "5000"},
            ],
        },
    ]


def tasks_due():
    """Two tasks: one due 2026-07-24 (target day), one overdue from 07-20."""
    return {
        "data": [
            {
                "id": 801, "name": "File discovery responses",
                "status": "pending", "priority": "High",
                "due_at": "2026-07-20T17:00:00Z",
                "assignee": {"id": 1, "name": "Shobin Clark"},
                "matter": {"id": 9001, "display_number": "2026-001"},
            },
            {
                "id": 802, "name": "Call client re settlement posture",
                "status": "pending", "priority": "Normal",
                "due_at": "2026-07-24T20:00:00Z",
                "assignee": {"id": 1, "name": "Shobin Clark"},
                "matter": {"id": 9004, "display_number": "2025-047"},
            },
        ]
    }


def calendar_entries():
    return {
        "data": [
            {
                "id": 901, "summary": "Status conference",
                "description": "Courtroom 4B",
                "start_at": "2026-07-24T14:00:00Z",
                "end_at": "2026-07-24T15:00:00Z",
                "all_day": False, "location": "Suffolk Superior Court",
                "matter": {"id": 9001, "display_number": "2026-001"},
            },
            {
                "id": 902, "summary": "New client intake: estate plan",
                "description": None,
                "start_at": "2026-07-24T18:30:00Z",
                "end_at": "2026-07-24T19:00:00Z",
                "all_day": False, "location": "Office",
                "matter": None,
            },
        ]
    }
