"""Stripe webhook handler must be idempotent.

Verifies the fix for issue #11 from the review: a duplicate event ID
from Stripe must short-circuit without re-applying side effects.
"""

from unittest.mock import patch


FAKE_EVENT = {
    "id": "evt_test_duplicate",
    "type": "invoice.payment_failed",
    "data": {"object": {"customer": "cus_test_none"}},
}


def _patch_construct_event():
    """Return a context manager that makes stripe.Webhook.construct_event
    return FAKE_EVENT regardless of payload/signature."""
    return patch("stripe.Webhook.construct_event", return_value=FAKE_EVENT)


def test_webhook_records_event_and_dedupes(client, app):
    from app.extensions import db
    from app.models.stripe_webhook_event import StripeWebhookEvent

    with _patch_construct_event():
        r1 = client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "stub"})
    assert r1.status_code == 200
    assert r1.get_json().get("status") == "ok"

    # First delivery recorded the event
    with app.app_context():
        evt = db.session.get(StripeWebhookEvent, FAKE_EVENT["id"])
        assert evt is not None
        assert evt.event_type == "invoice.payment_failed"

    # Second delivery should short-circuit
    with _patch_construct_event():
        r2 = client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "stub"})
    assert r2.status_code == 200
    assert r2.get_json().get("status") == "already_processed"


def test_webhook_rolls_back_on_handler_failure(client, app):
    """If a handler raises, we must NOT record the event — otherwise
    Stripe's retry would be silently dropped."""
    from app.extensions import db
    from app.models.stripe_webhook_event import StripeWebhookEvent

    with _patch_construct_event():
        with patch(
            "app.routes.billing.handle_payment_failed",
            side_effect=RuntimeError("boom"),
        ):
            # We expect the exception to propagate — the framework turns it
            # into a 500. The important invariant is that the event row
            # was NOT written.
            try:
                client.post("/billing/webhook", data=b"{}", headers={"Stripe-Signature": "stub"})
            except Exception:
                pass

    with app.app_context():
        evt = db.session.get(StripeWebhookEvent, FAKE_EVENT["id"])
        assert evt is None
