from datetime import datetime

from app.extensions import db


class AuditLog(db.Model):
    """Append-only security audit trail: who did what, from where, and when.

    Insert-only by convention — no code path updates or deletes rows. Captures
    authentication events and sensitive-data access (report generation and
    downloads, the trust report especially) for security-review / SOC 2
    readiness. Queryable by user, action, and time.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_email = db.Column(db.String(255), nullable=True, index=True)
    # e.g. login, logout, report.generate, report.download
    action = db.Column(db.String(64), nullable=False, index=True)
    resource_type = db.Column(db.String(64), nullable=True)  # e.g. "report"
    resource_id = db.Column(db.String(100), nullable=True)
    detail = db.Column(db.String(500), nullable=True)  # e.g. report_type
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_email} at={self.created_at}>"
