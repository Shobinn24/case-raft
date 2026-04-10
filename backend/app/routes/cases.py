from flask import Blueprint, jsonify, request

from app.utils.auth import get_clio_client, unauthenticated_response

cases_bp = Blueprint("cases", __name__)


@cases_bp.route("/cases")
def list_cases():
    """List all open matters from Clio."""
    clio, _ = get_clio_client()
    if not clio:
        return unauthenticated_response()
    status = request.args.get("status", "open,pending,closed")
    data = clio.get_matters(status=status)
    return jsonify(data)


@cases_bp.route("/cases/<int:case_id>")
def get_case(case_id):
    """Get a single matter with full details."""
    clio, _ = get_clio_client()
    if not clio:
        return unauthenticated_response()
    data = clio.get_matter(case_id)
    return jsonify(data)
