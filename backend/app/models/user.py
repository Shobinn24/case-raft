import os
from datetime import datetime

from app.extensions import db


def _env_set(name, default):
    """Parse a comma-separated env var into a lowercased set. Falls back to default."""
    raw = os.environ.get(name, default)
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


# Defaults preserved from the previous hardcoded lists so behavior doesn't
# change unless the env var is explicitly set.
_DEFAULT_WHITELISTED_DOMAINS = "trustice.us"
_DEFAULT_WHITELISTED_EMAILS = "srhoades@trustice.us,shobinn24@gmail.com,shobinn@eclarx.com"
_DEFAULT_ADMIN_EMAILS = "shobinn24@gmail.com"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    clio_access_token = db.Column(db.Text, nullable=False)
    clio_refresh_token = db.Column(db.Text, nullable=False)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Stripe subscription fields
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    subscription_status = db.Column(db.String(50), default="free")  # free, active, past_due, canceled
    plan_tier = db.Column(db.String(50), default="free")  # free, solo, team, firm

    is_admin = db.Column(db.Boolean, default=False)
    timezone = db.Column(db.String(50), nullable=True)  # e.g. "Eastern Time (US & Canada)"

    reports = db.relationship("ReportHistory", backref="user", lazy=True)

    # Whitelisted domains/emails — env var overrides the default list
    WHITELISTED_DOMAINS = _env_set("WHITELISTED_DOMAINS", _DEFAULT_WHITELISTED_DOMAINS)
    WHITELISTED_EMAILS = _env_set("WHITELISTED_EMAILS", _DEFAULT_WHITELISTED_EMAILS)

    # Admin emails get access to the admin dashboard
    ADMIN_EMAILS = _env_set("ADMIN_EMAILS", _DEFAULT_ADMIN_EMAILS)

    @property
    def check_is_admin(self):
        if not self.email:
            return False
        return self.email.lower() in self.ADMIN_EMAILS or self.is_admin

    @property
    def is_whitelisted(self):
        if not self.email:
            return False
        email_lower = self.email.lower()
        if email_lower in self.WHITELISTED_EMAILS:
            return True
        domain = email_lower.split("@")[-1]
        return domain in self.WHITELISTED_DOMAINS

    @property
    def is_paid(self):
        if self.is_whitelisted:
            return True
        return self.subscription_status == "active" and self.plan_tier != "free"

    @property
    def effective_plan_tier(self):
        if self.is_whitelisted:
            return "firm"
        return self.plan_tier

    def __repr__(self):
        return f"<User {self.email}>"
