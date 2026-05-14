"""Shared auth helpers used by route modules."""

from functools import wraps

from flask import jsonify, session

from app.models.user import User
from app.services.clio_client import ClioAPIClient


def get_clio_client():
    """Build a ClioAPIClient from the current session user.

    Returns (client, user) on success or (None, None) if no authenticated
    user. Route handlers should check the client is not None and return a
    401 otherwise.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, None
    user = User.query.get(user_id)
    if not user:
        return None, None
    client = ClioAPIClient(
        access_token=user.clio_access_token,
        refresh_token=user.clio_refresh_token,
        token_expires_at=user.token_expires_at,
        user_id=user.id,
    )
    return client, user


def unauthenticated_response():
    return jsonify({"error": "Not authenticated"}), 401


# ---------------------------------------------------------------------------
# Subscription gate decorators
# ---------------------------------------------------------------------------
# Use these on any new route that requires a paid subscription, rather than
# inline `_require_subscription(user)` style calls. The decorator pattern
# means new blueprints can't accidentally skip the gate — applying it is
# explicit and grep-able.
#
# Admin + whitelisted users automatically bypass (handled by user.is_paid).

def _subscription_required_response():
    return jsonify({
        "error": "Subscription required",
        "message": "An active subscription is required to use this feature. Please choose a plan.",
        "upgrade": True,
    }), 403


def _tier_upgrade_response(feature_name):
    return jsonify({
        "error": "Plan upgrade required",
        "message": f"{feature_name} requires a Team or Firm plan.",
        "upgrade": True,
    }), 403


def _current_user_or_401():
    """Resolve the current session user, or return a 401 response tuple.

    Returns either (user, None) on success or (None, response_tuple) on
    failure.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None, unauthenticated_response()
    user = User.query.get(user_id)
    if not user:
        return None, unauthenticated_response()
    return user, None


def require_subscription(view_func):
    """Decorator: route requires an active paid subscription (or admin /
    whitelist bypass via user.is_paid)."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        user, err = _current_user_or_401()
        if err:
            return err
        if not user.is_paid:
            return _subscription_required_response()
        return view_func(*args, **kwargs)
    return wrapped


def require_tier(*allowed_tiers, feature_name="This feature"):
    """Decorator factory: route requires `user.effective_plan_tier` to be in
    `allowed_tiers`. Implies require_subscription. Admin + whitelisted users
    map to firm tier (see user.effective_plan_tier)."""
    allowed = set(allowed_tiers)
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user, err = _current_user_or_401()
            if err:
                return err
            if not user.is_paid:
                return _subscription_required_response()
            if user.effective_plan_tier not in allowed:
                return _tier_upgrade_response(feature_name)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
