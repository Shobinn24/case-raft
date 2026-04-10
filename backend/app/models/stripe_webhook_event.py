from datetime import datetime

from app.extensions import db


class StripeWebhookEvent(db.Model):
    """Records every Stripe webhook event we've processed so we can
    short-circuit duplicate deliveries. Stripe guarantees at-least-once
    delivery, so without this table we'd double-apply plan changes, etc.
    """

    __tablename__ = "stripe_webhook_events"

    id = db.Column(db.String(255), primary_key=True)  # Stripe event ID
    event_type = db.Column(db.String(100))
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<StripeWebhookEvent {self.id} {self.event_type}>"
