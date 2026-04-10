"""Shared auth helpers used by route modules."""

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
