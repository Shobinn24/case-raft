"""Tests for the append-only audit log (app/services/audit.py)."""


def test_record_audit_writes_row(app):
    from app.models.audit_log import AuditLog
    from app.services.audit import record_audit

    with app.test_request_context("/", headers={"User-Agent": "pytest-agent"}):
        record_audit(
            "report.generate",
            user_email="sarah@example.com",
            resource_type="report",
            resource_id=42,
            detail="trust_management",
        )

    rows = AuditLog.query.all()
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "report.generate"
    assert row.user_email == "sarah@example.com"
    assert row.resource_type == "report"
    assert row.resource_id == "42"  # coerced to string
    assert row.detail == "trust_management"
    assert row.user_agent == "pytest-agent"
    assert row.created_at is not None


def test_record_audit_uses_user_object(app, make_user):
    from app.models.audit_log import AuditLog
    from app.services.audit import record_audit

    user = make_user(email="login@example.com")
    with app.test_request_context("/"):
        record_audit("login", user=user)

    row = AuditLog.query.filter_by(action="login").first()
    assert row is not None
    assert row.user_id == user.id
    assert row.user_email == "login@example.com"


def test_record_audit_never_raises(app):
    """An audit failure must never propagate into the caller."""
    from app.services.audit import record_audit

    # No request context, and a non-string detail — must not raise.
    record_audit("weird_action", detail=12345)
