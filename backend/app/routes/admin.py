from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import func

from app.extensions import db
from app.models.error_log import ErrorLog
from app.models.report_history import ReportHistory
from app.models.user import User

admin_bp = Blueprint("admin", __name__)


def _require_admin():
    """Check if the current user is an admin. Returns (user, error_response)."""
    user_id = session.get("user_id")
    if not user_id:
        return None, (jsonify({"error": "Not authenticated"}), 401)
    user = User.query.get(user_id)
    if not user:
        return None, (jsonify({"error": "Not authenticated"}), 401)
    if not user.check_is_admin:
        return None, (jsonify({"error": "Admin access required"}), 403)
    return user, None


@admin_bp.route("/stats")
def admin_stats():
    """Dashboard summary stats."""
    user, error = _require_admin()
    if error:
        return error

    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    total_users = User.query.count()
    active_subscribers = User.query.filter(
        User.subscription_status == "active",
        User.plan_tier != "free",
    ).count()

    errors_24h = ErrorLog.query.filter(ErrorLog.created_at >= last_24h).count()
    errors_7d = ErrorLog.query.filter(ErrorLog.created_at >= last_7d).count()
    errors_total = ErrorLog.query.count()

    total_reports = ReportHistory.query.count()

    return jsonify({
        "total_users": total_users,
        "active_subscribers": active_subscribers,
        "errors_24h": errors_24h,
        "errors_7d": errors_7d,
        "errors_total": errors_total,
        "total_reports": total_reports,
    })


@admin_bp.route("/errors")
def admin_errors():
    """List error logs with filtering and pagination."""
    user, error = _require_admin()
    if error:
        return error

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    per_page = min(per_page, 100)

    query = ErrorLog.query

    # Filters
    status_filter = request.args.get("status")
    if status_filter == "4xx":
        query = query.filter(ErrorLog.status_code >= 400, ErrorLog.status_code < 500)
    elif status_filter == "5xx":
        query = query.filter(ErrorLog.status_code >= 500)

    email_filter = request.args.get("email")
    if email_filter:
        query = query.filter(ErrorLog.user_email.ilike(f"%{email_filter}%"))

    endpoint_filter = request.args.get("endpoint")
    if endpoint_filter:
        query = query.filter(ErrorLog.endpoint.ilike(f"%{endpoint_filter}%"))

    start_date = request.args.get("start_date")
    if start_date:
        query = query.filter(ErrorLog.created_at >= start_date)

    end_date = request.args.get("end_date")
    if end_date:
        query = query.filter(ErrorLog.created_at <= end_date)

    # Order by most recent
    query = query.order_by(ErrorLog.created_at.desc())

    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "errors": [e.to_dict() for e in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
        "per_page": per_page,
    })


@admin_bp.route("/errors/<int:error_id>")
def admin_error_detail(error_id):
    """Get a single error log with full detail."""
    user, error = _require_admin()
    if error:
        return error

    log = ErrorLog.query.get(error_id)
    if not log:
        return jsonify({"error": "Error log not found"}), 404

    return jsonify(log.to_dict())


@admin_bp.route("/clio-fields-debug")
def clio_fields_debug():
    """Temporary debug endpoint to discover Clio API field structures for trust data."""
    user, error = _require_admin()
    if error:
        return error

    from app.services.clio_client import ClioAPIClient

    clio = ClioAPIClient(
        access_token=user.clio_access_token,
        refresh_token=user.clio_refresh_token,
        token_expires_at=user.token_expires_at,
        user_id=user.id,
    )

    results = {}

    # V3: Try outstanding_client_balances with explicit fields
    try:
        resp = clio._request("GET", "outstanding_client_balances.json", params={
            "fields": "id,contact,last_payment,newest_outstanding_bill,"
                      "newest_outstanding_balance,pending_payments,"
                      "total_outstanding_balance,trust_balance",
            "limit": 5,
        })
        results["outstanding_balances_with_fields"] = resp.get("data", [])
    except Exception as e:
        results["outstanding_balances_with_fields_error"] = str(e)

    # V3: Try outstanding_client_balances with no fields (see defaults)
    try:
        resp = clio._request("GET", "outstanding_client_balances.json", params={
            "limit": 5,
        })
        results["outstanding_balances_default"] = resp.get("data", [])
    except Exception as e:
        results["outstanding_balances_default_error"] = str(e)

    # V3: Try trust_line_items with corrected order (id instead of date)
    try:
        resp = clio._request("GET", "trust_line_items.json", params={
            "fields": "id,date,total,note,"
                      "matter{id,display_number}",
            "limit": 5,
            "order": "id(desc)",
        })
        results["trust_line_items"] = resp.get("data", [])
    except Exception as e:
        results["trust_line_items_error"] = str(e)

    # V3: Try matters with billing_setting nested object
    try:
        resp = clio._request("GET", "matters.json", params={
            "fields": "id,display_number,status,"
                      "client{id,name},"
                      "billing_setting,"
                      "evergreen_retainer,"
                      "custom_field_values{id,field_name,value}",
            "status": "open",
            "limit": 5,
            "order": "id(asc)",
        })
        results["matters_with_billing_setting"] = resp.get("data", [])
    except Exception as e:
        results["matters_with_billing_setting_error"] = str(e)

    # V3: Try matter-level trust request with different sub-fields
    try:
        resp = clio._request("GET", "matters.json", params={
            "fields": "id,display_number,"
                      "trust_balance,"
                      "account_balances{id,name,balance,type,current_balance}",
            "status": "open",
            "limit": 2,
            "order": "id(asc)",
        })
        results["matters_trust_balance_field"] = resp.get("data", [])
    except Exception as e:
        results["matters_trust_balance_field_error"] = str(e)

    # V3: Try contacts endpoint for trust balance (some APIs put it on contacts)
    try:
        resp = clio._request("GET", "contacts.json", params={
            "fields": "id,name,type,"
                      "trust_balance,"
                      "outstanding_balance,"
                      "account_balances",
            "type": "Company",
            "limit": 5,
        })
        results["contacts_with_balances"] = resp.get("data", [])
    except Exception as e:
        results["contacts_with_balances_error"] = str(e)

    return jsonify(results)


@admin_bp.route("/users")
def admin_users():
    """List all registered users with report counts."""
    user, error = _require_admin()
    if error:
        return error

    users = User.query.order_by(User.created_at.desc()).all()

    # Get report counts per user
    report_counts = dict(
        db.session.query(
            ReportHistory.user_id, func.count(ReportHistory.id)
        ).group_by(ReportHistory.user_id).all()
    )

    # Get error counts per user
    error_counts = dict(
        db.session.query(
            ErrorLog.user_id, func.count(ErrorLog.id)
        ).filter(ErrorLog.user_id.isnot(None))
        .group_by(ErrorLog.user_id).all()
    )

    return jsonify({
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "plan_tier": u.effective_plan_tier,
                "subscription_status": u.subscription_status,
                "is_admin": u.check_is_admin,
                "is_whitelisted": u.is_whitelisted,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "updated_at": u.updated_at.isoformat() if u.updated_at else None,
                "report_count": report_counts.get(u.id, 0),
                "error_count": error_counts.get(u.id, 0),
            }
            for u in users
        ]
    })
