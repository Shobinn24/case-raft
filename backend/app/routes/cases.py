from flask import Blueprint, jsonify, request, session

from app.models.user import User
from app.services.clio_client import ClioAPIClient

cases_bp = Blueprint("cases", __name__)


def _get_clio_client():
    """Build a ClioAPIClient from the current session user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = User.query.get(user_id)
    if not user:
        return None
    return ClioAPIClient(
        access_token=user.clio_access_token,
        refresh_token=user.clio_refresh_token,
        token_expires_at=user.token_expires_at,
        user_id=user.id,
    )


@cases_bp.route("/cases")
def list_cases():
    """List all open matters from Clio."""
    clio = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401
    status = request.args.get("status", "open,pending,closed")
    data = clio.get_matters(status=status)
    return jsonify(data)


@cases_bp.route("/cases/<int:case_id>")
def get_case(case_id):
    """Get a single matter with full details."""
    clio = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401
    data = clio.get_matter(case_id)
    return jsonify(data)
