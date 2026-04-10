import stripe
from flask import current_app

from app.extensions import db
from app.models.user import User


def _init_stripe():
    stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]


def get_or_create_customer(user):
    """Get existing Stripe customer or create a new one."""
    _init_stripe()
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(email=user.email)
    user.stripe_customer_id = customer.id
    db.session.commit()
    return customer.id


def create_checkout_session(user, price_id, success_url, cancel_url):
    """Create a Stripe Checkout session for a subscription."""
    _init_stripe()
    customer_id = get_or_create_customer(user)

    params = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"user_id": str(user.id)},
    }

    # Apply coupon if configured
    coupon_id = current_app.config.get("STRIPE_COUPON_ID")
    if coupon_id:
        params["discounts"] = [{"coupon": coupon_id}]

    session = stripe.checkout.Session.create(**params)
    return session


def create_portal_session(user, return_url):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    _init_stripe()
    if not user.stripe_customer_id:
        return None

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url,
    )
    return session


def handle_checkout_completed(session_data):
    """Process a completed checkout session."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.stripe_subscription_id = subscription_id
    user.subscription_status = "active"

    # Determine plan tier from the subscription
    _init_stripe()
    subscription = stripe.Subscription.retrieve(subscription_id)
    price_id = subscription["items"]["data"][0]["price"]["id"]
    user.plan_tier = _price_to_tier(price_id)

    db.session.commit()


def handle_subscription_updated(subscription_data):
    """Process subscription updates (plan changes, renewals, failures)."""
    customer_id = subscription_data.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    status = subscription_data.get("status")
    # Map Stripe statuses to our simplified statuses
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete": "free",
        "incomplete_expired": "canceled",
        "trialing": "active",
    }
    user.subscription_status = status_map.get(status, "free")

    if status in ("canceled", "incomplete_expired"):
        user.plan_tier = "free"
    else:
        price_id = subscription_data["items"]["data"][0]["price"]["id"]
        user.plan_tier = _price_to_tier(price_id)

    db.session.commit()


def handle_subscription_deleted(subscription_data):
    """Process subscription cancellation."""
    customer_id = subscription_data.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.subscription_status = "canceled"
    user.plan_tier = "free"
    user.stripe_subscription_id = None
    db.session.commit()


def handle_payment_failed(invoice_data):
    """Process a failed payment."""
    customer_id = invoice_data.get("customer")
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        return

    user.subscription_status = "past_due"
    db.session.commit()


def _price_to_tier(price_id):
    """Map a Stripe price ID to our internal tier name.

    Returns "free" (not "solo") for unknown price IDs so a misconfigured
    Stripe dashboard can never silently grant paid access.
    """
    price_map = {
        current_app.config["STRIPE_PRICE_SOLO"]: "solo",
        current_app.config["STRIPE_PRICE_TEAM"]: "team",
        current_app.config["STRIPE_PRICE_FIRM"]: "firm",
    }
    tier = price_map.get(price_id)
    if not tier:
        current_app.logger.error(
            f"Unknown Stripe price ID: {price_id}. "
            f"Expected one of: {list(price_map.keys())}"
        )
        return "free"  # Safe default — don't silently grant access
    return tier
