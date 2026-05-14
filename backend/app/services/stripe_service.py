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


def _extract_price_id(subscription_data):
    """Safely pull the first line item's price ID from a Stripe subscription
    payload. Returns None if the path is missing or items.data is empty —
    avoids KeyError-into-Stripe-retry-loop on incomplete subs."""
    items = subscription_data.get("items") or {}
    data = items.get("data") or []
    if not data:
        return None
    price = data[0].get("price") or {}
    return price.get("id")


def _find_user_by_customer(customer_id, event_type):
    """Look up the user record by Stripe customer ID. Logs (not silently
    returns) if no user is found — the prior behavior of silent-return meant
    a real customer who existed under a different user record never got
    their subscription state synced, with no visibility."""
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if not user:
        current_app.logger.warning(
            "stripe webhook: no user found for customer_id=%s (event=%s). "
            "Subscription state will not be synced for this customer.",
            customer_id, event_type,
        )
    return user


def handle_checkout_completed(session_data):
    """Process a completed checkout session."""
    customer_id = session_data.get("customer")
    subscription_id = session_data.get("subscription")

    user = _find_user_by_customer(customer_id, "checkout.session.completed")
    if not user:
        return

    user.stripe_subscription_id = subscription_id
    user.subscription_status = "active"

    # Determine plan tier from the subscription
    _init_stripe()
    subscription = stripe.Subscription.retrieve(subscription_id)
    price_id = _extract_price_id(subscription)
    user.plan_tier = _price_to_tier(price_id) if price_id else "free"

    db.session.commit()


def handle_subscription_updated(subscription_data):
    """Process subscription updates (plan changes, renewals, failures)."""
    customer_id = subscription_data.get("customer")
    user = _find_user_by_customer(customer_id, "customer.subscription.updated")
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
        "paused": "free",
    }
    user.subscription_status = status_map.get(status, "free")

    if status in ("canceled", "incomplete_expired"):
        user.plan_tier = "free"
    else:
        price_id = _extract_price_id(subscription_data)
        user.plan_tier = _price_to_tier(price_id) if price_id else "free"

    db.session.commit()


def handle_subscription_created(subscription_data):
    """Process subscription creation. Stripe fires this for subs created via
    Dashboard or admin flows (not just Checkout) — without this handler,
    those subs would silently leave the user in 'free' state. Functionally
    identical to handle_subscription_updated."""
    handle_subscription_updated(subscription_data)


def handle_subscription_deleted(subscription_data):
    """Process subscription cancellation.

    Guards against the out-of-order race: if Stripe delivers a stale
    `subscription.deleted` for an OLD subscription ID after the user has
    already re-subscribed (which would create a NEW subscription with a
    new ID), ignore it instead of wiping the active subscription state.
    Audit finding 2026-05-14 P0 #1.
    """
    customer_id = subscription_data.get("customer")
    deleted_sub_id = subscription_data.get("id")
    user = _find_user_by_customer(customer_id, "customer.subscription.deleted")
    if not user:
        return

    if user.stripe_subscription_id and user.stripe_subscription_id != deleted_sub_id:
        # Stale delete event for a subscription that's already been replaced.
        # Logging at info level so we have a trail; this is expected during
        # quick cancel+resubscribe flows.
        current_app.logger.info(
            "stripe webhook: ignoring stale subscription.deleted for "
            "customer=%s deleted_sub=%s (user is now on sub=%s)",
            customer_id, deleted_sub_id, user.stripe_subscription_id,
        )
        return

    user.subscription_status = "canceled"
    user.plan_tier = "free"
    user.stripe_subscription_id = None
    db.session.commit()


def handle_payment_failed(invoice_data):
    """Process a failed payment."""
    customer_id = invoice_data.get("customer")
    user = _find_user_by_customer(customer_id, "invoice.payment_failed")
    if not user:
        return

    user.subscription_status = "past_due"
    db.session.commit()


def handle_payment_succeeded(invoice_data):
    """Process a successful payment — recovers a `past_due` user to `active`
    without waiting for the (possibly delayed) `customer.subscription.updated`
    event that Stripe normally also sends. Audit finding 2026-05-14 P1 #6."""
    customer_id = invoice_data.get("customer")
    user = _find_user_by_customer(customer_id, "invoice.payment_succeeded")
    if not user:
        return

    # Only flip status if currently past_due. Leave 'active' / 'trialing'
    # / 'canceled' alone (canceled invoices shouldn't fire payment_succeeded
    # but defense in depth).
    if user.subscription_status == "past_due":
        user.subscription_status = "active"
        db.session.commit()


def handle_trial_will_end(subscription_data):
    """Stub: Stripe fires this ~3 days before a trial ends. Eventually this
    should enqueue a notification email so users know their card will be
    charged. For now we just log — the user.subscription_status is unaffected
    until the trial actually ends and a new event fires."""
    customer_id = subscription_data.get("customer")
    user = _find_user_by_customer(customer_id, "customer.subscription.trial_will_end")
    if not user:
        return
    current_app.logger.info(
        "stripe webhook: trial_will_end fired for customer=%s user=%s. "
        "TODO: send trial-ending notification email.",
        customer_id, user.email,
    )


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
