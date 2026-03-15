from datetime import datetime

from app.extensions import db


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

    reports = db.relationship("ReportHistory", backref="user", lazy=True)

    @property
    def is_paid(self):
        return self.subscription_status == "active" and self.plan_tier != "free"

    def __repr__(self):
        return f"<User {self.email}>"
