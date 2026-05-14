"""Tests for the Stripe webhook handler mutation logic.

`test_webhook_idempotency.py` already covers the idempotency / replay /
rollback invariants. This file covers the per-event-type mutation
behavior surfaced by the 2026-05-14 audit:

  - P0 #1: out-of-order subscription.deleted for a stale sub ID must
    NOT wipe the user's currently-active subscription.
  - P1 #6: invoice.payment_succeeded recovers past_due → active.
  - P1 #6: customer.subscription.created is now handled.
  - P1 #7: malformed `subscription.items.data[0].price.id` no longer
    raises KeyError (defensive .get() chain).
"""

from unittest.mock import patch

from app.services.stripe_service import (
    handle_payment_succeeded,
    handle_subscription_created,
    handle_subscription_deleted,
    handle_subscription_updated,
)


# ---------------------------------------------------------------------------
# P0 #1 — stale subscription.deleted must not wipe an active sub
# ---------------------------------------------------------------------------

def test_subscription_deleted_ignores_stale_event(app, make_user):
    """Cancel + resubscribe flow: an old `subscription.deleted` arriving
    AFTER the user's new checkout creates a new sub must not wipe state."""
    from app.extensions import db

    user = make_user(
        email="cycler@example.com",
        plan_tier="team",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_cycler"
    user.stripe_subscription_id = "sub_NEW"
    db.session.commit()

    # Stripe delivers a stale delete for the OLD sub
    handle_subscription_deleted({
        "customer": "cus_cycler",
        "id": "sub_OLD",
    })
    db.session.refresh(user)

    assert user.subscription_status == "active"
    assert user.plan_tier == "team"
    assert user.stripe_subscription_id == "sub_NEW"


def test_subscription_deleted_applies_when_id_matches(app, make_user):
    """When the deleted sub IS the user's current sub, the wipe applies."""
    from app.extensions import db

    user = make_user(
        plan_tier="team",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_real_cancel"
    user.stripe_subscription_id = "sub_CURRENT"
    db.session.commit()

    handle_subscription_deleted({
        "customer": "cus_real_cancel",
        "id": "sub_CURRENT",
    })
    db.session.refresh(user)

    assert user.subscription_status == "canceled"
    assert user.plan_tier == "free"
    assert user.stripe_subscription_id is None


# ---------------------------------------------------------------------------
# P1 #6 — invoice.payment_succeeded recovers past_due → active
# ---------------------------------------------------------------------------

def test_payment_succeeded_recovers_past_due(app, make_user):
    from app.extensions import db

    user = make_user(
        plan_tier="solo",
        subscription_status="past_due",
    )
    user.stripe_customer_id = "cus_recovered"
    db.session.commit()

    handle_payment_succeeded({"customer": "cus_recovered"})
    db.session.refresh(user)

    assert user.subscription_status == "active"


def test_payment_succeeded_leaves_active_unchanged(app, make_user):
    """Don't flip 'trialing' or 'canceled' or other states — only past_due."""
    from app.extensions import db

    user = make_user(
        plan_tier="solo",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_already_active"
    db.session.commit()

    handle_payment_succeeded({"customer": "cus_already_active"})
    db.session.refresh(user)

    assert user.subscription_status == "active"


def test_payment_succeeded_leaves_canceled_alone(app, make_user):
    from app.extensions import db

    user = make_user(
        plan_tier="free",
        subscription_status="canceled",
    )
    user.stripe_customer_id = "cus_canceled"
    db.session.commit()

    handle_payment_succeeded({"customer": "cus_canceled"})
    db.session.refresh(user)

    assert user.subscription_status == "canceled"


# ---------------------------------------------------------------------------
# P1 #6 — customer.subscription.created handler
# ---------------------------------------------------------------------------

def test_subscription_created_syncs_user_state(app, make_user):
    """A subscription created in the Stripe Dashboard (not via Checkout)
    should flip the user to active — same logic as updated."""
    from app.extensions import db

    user = make_user(
        plan_tier="free",
        subscription_status="free",
    )
    user.stripe_customer_id = "cus_dashboard_sub"
    db.session.commit()

    handle_subscription_created({
        "customer": "cus_dashboard_sub",
        "id": "sub_dashboard",
        "status": "active",
        "items": {"data": [{"price": {"id": "price_team_stub"}}]},
    })
    db.session.refresh(user)

    assert user.subscription_status == "active"
    assert user.plan_tier == "team"


# ---------------------------------------------------------------------------
# P1 #7 — defensive guards on subscription.items.data[0].price.id
# ---------------------------------------------------------------------------

def test_subscription_updated_with_empty_items(app, make_user):
    """An 'incomplete' subscription from Stripe can have items.data = [].
    Pre-fix this raised IndexError; Stripe would retry forever."""
    from app.extensions import db

    user = make_user(
        plan_tier="solo",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_empty_items"
    db.session.commit()

    # Should not raise
    handle_subscription_updated({
        "customer": "cus_empty_items",
        "status": "incomplete",
        "items": {"data": []},
    })
    db.session.refresh(user)

    # incomplete -> "free" per status_map; empty items -> plan_tier="free"
    assert user.subscription_status == "free"
    assert user.plan_tier == "free"


def test_subscription_updated_with_missing_items_key(app, make_user):
    """A schema drift where `items` is missing entirely."""
    from app.extensions import db

    user = make_user(
        plan_tier="team",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_no_items"
    db.session.commit()

    # Should not raise
    handle_subscription_updated({
        "customer": "cus_no_items",
        "status": "active",
        # items omitted entirely
    })
    db.session.refresh(user)

    assert user.plan_tier == "free"  # missing price → safe default


def test_subscription_updated_handles_paused_status(app, make_user):
    """Stripe's pause-collection feature emits status='paused' which
    previously fell through to 'free' default. Now explicit in status_map."""
    from app.extensions import db

    user = make_user(
        plan_tier="team",
        subscription_status="active",
    )
    user.stripe_customer_id = "cus_paused"
    db.session.commit()

    handle_subscription_updated({
        "customer": "cus_paused",
        "status": "paused",
        "items": {"data": [{"price": {"id": "price_team_stub"}}]},
    })
    db.session.refresh(user)

    assert user.subscription_status == "free"
