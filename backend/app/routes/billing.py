import stripe
from flask import Blueprint, current_app, jsonify, request, session

from app.extensions import db
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.user import User
from app.services.stripe_service import (
    create_checkout_session,
    create_portal_session,
    handle_checkout_completed,
    handle_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)

billing_bp = Blueprint("billing", __name__)


@billing_bp.route("/checkout", methods=["POST"])
def checkout():
    """Create a Stripe Checkout session for the selected plan."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    tier = data.get("tier") if data else None
    if tier not in ("solo", "team", "firm"):
        return jsonify({"error": "Invalid tier. Must be solo, team, or firm"}), 400

    price_map = {
        "solo": current_app.config["STRIPE_PRICE_SOLO"],
        "team": current_app.config["STRIPE_PRICE_TEAM"],
        "firm": current_app.config["STRIPE_PRICE_FIRM"],
    }
    price_id = price_map[tier]

    # Build success/cancel URLs relative to the request origin
    origin = request.headers.get("Origin", request.host_url.rstrip("/"))
    success_url = f"{origin}/billing?status=success"
    cancel_url = f"{origin}/pricing?status=canceled"

    try:
        checkout_session = create_checkout_session(user, price_id, success_url, cancel_url)
        return jsonify({"checkout_url": checkout_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/portal", methods=["POST"])
def portal():
    """Create a Stripe Customer Portal session for managing subscriptions."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if not user.stripe_customer_id:
        return jsonify({"error": "No active subscription"}), 400

    origin = request.headers.get("Origin", request.host_url.rstrip("/"))
    return_url = f"{origin}/billing"

    try:
        portal_session = create_portal_session(user, return_url)
        return jsonify({"portal_url": portal_session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@billing_bp.route("/subscription")
def subscription():
    """Get the current user's subscription status."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "subscription_status": user.subscription_status,
        "plan_tier": user.plan_tier,
        "is_paid": user.is_paid,
    })


@billing_bp.route("/prices")
def prices():
    """Return the available plan prices (public endpoint — no auth required)."""
    return jsonify({
        "plans": [
            {
                "tier": "solo",
                "name": "Solo",
                "price": 29,
                "description": "1 user",
                "features": [
                    "Case summary reports",
                    "Basic firm productivity reports",
                    "Report download history",
                    "PDF export",
                ],
            },
            {
                "tier": "team",
                "name": "Team",
                "price": 79,
                "description": "Up to 5 users",
                "features": [
                    "Everything in Solo",
                    "Full analytics suite",
                    "Batch report generation",
                    "CSV export (QuickBooks/Xero)",
                    "Collected revenue reports",
                ],
            },
            {
                "tier": "firm",
                "name": "Firm",
                "price": 149,
                "description": "Unlimited users",
                "features": [
                    "Everything in Team",
                    "Unlimited report generation",
                    "Custom report sections",
                    "Priority support",
                    "Aging receivables analysis",
                ],
            },
        ],
    })


@billing_bp.route("/webhook", methods=["POST"])
def webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event["type"]
    event_id = event["id"]
    data = event["data"]["object"]

    # Idempotency — Stripe guarantees at-least-once delivery, so we must
    # short-circuit duplicate deliveries before re-applying side effects.
    if StripeWebhookEvent.query.get(event_id):
        return jsonify({"status": "already_processed"}), 200

    try:
        if event_type == "checkout.session.completed":
            handle_checkout_completed(data)
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(data)
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(data)
        elif event_type == "invoice.payment_failed":
            handle_payment_failed(data)

        # Record the event only after successful processing so a failed
        # handler gets retried by Stripe instead of being silently skipped.
        db.session.add(StripeWebhookEvent(id=event_id, event_type=event_type))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"status": "ok"}), 200
