import os

from flask import Blueprint, jsonify, request, send_file, session, current_app

from app.models.report_history import ReportHistory
from app.models.user import User
from app.services.clio_client import ClioAPIClient
from app.services.firm_data import FirmProductivityData
from app.services.report import CaseSummaryReport, FirmProductivityReport

reports_bp = Blueprint("reports", __name__)


def _get_clio_client():
    """Build a ClioAPIClient from the current session user."""
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


@reports_bp.route("/reports/generate", methods=["POST"])
def generate_report():
    """Generate a PDF report for a given case."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data or "case_id" not in data:
        return jsonify({"error": "case_id is required"}), 400

    case_id = data["case_id"]
    report_type = data.get("report_type", "case_summary")

    # Fetch full case details from Clio
    case_data = clio.get_matter(case_id)
    if "data" not in case_data:
        return jsonify({"error": "Failed to fetch case data from Clio"}), 502

    # Fetch related contacts (opposing parties, counsel, court contacts)
    related_contacts = []
    try:
        rc_resp = clio.get_related_contacts(case_id)
        related_contacts = rc_resp.get("data", [])
    except Exception:
        pass  # Non-critical — report still works without relationships

    # Fetch billing data (invoices and time entries)
    bills = []
    activities = []
    try:
        bills_resp = clio.get_bills(case_id)
        bills = bills_resp.get("data", [])
    except Exception:
        pass
    try:
        activities_resp = clio.get_activities(case_id)
        activities = activities_resp.get("data", [])
    except Exception:
        pass

    # Generate report
    report_classes = {
        "case_summary": CaseSummaryReport,
    }
    report_cls = report_classes.get(report_type)
    if not report_cls:
        return jsonify({"error": f"Unknown report type: {report_type}"}), 400

    report = report_cls(
        case_data["data"], user.id,
        related_contacts=related_contacts,
        bills=bills,
        activities=activities,
    )
    record = report.generate()

    return jsonify({
        "message": "Report generated successfully",
        "report": {
            "id": record.id,
            "case_id": record.case_id,
            "case_name": record.case_name,
            "report_type": record.report_type,
            "generated_at": record.generated_at.isoformat(),
        },
    })


@reports_bp.route("/reports/generate-firm", methods=["POST"])
def generate_firm_report():
    """Generate a firm-wide PDF report for a given date range."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    report_type = data.get("report_type", "firm_productivity")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400

    # Fetch firm-wide data from Clio
    try:
        users_resp = clio.get_users()
        users_data = users_resp.get("data", [])
    except Exception as e:
        return jsonify({"error": f"Failed to fetch users: {str(e)}"}), 502

    try:
        activities_data = clio.get_all_activities(start_date, end_date)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch activities: {str(e)}"}), 502

    try:
        bills_data = clio.get_all_bills(start_date, end_date)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch bills: {str(e)}"}), 502

    # Build firm data model and generate report
    firm_data = FirmProductivityData(
        start_date, end_date, users_data, activities_data, bills_data
    )

    firm_report_classes = {
        "firm_productivity": FirmProductivityReport,
    }
    report_cls = firm_report_classes.get(report_type)
    if not report_cls:
        return jsonify({"error": f"Unknown report type: {report_type}"}), 400

    report = report_cls(firm_data, user.id)
    record = report.generate()

    return jsonify({
        "message": "Report generated successfully",
        "report": {
            "id": record.id,
            "case_name": record.case_name,
            "report_type": record.report_type,
            "generated_at": record.generated_at.isoformat(),
        },
    })


@reports_bp.route("/reports/history")
def report_history():
    """List all reports generated by the current user."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    reports = (
        ReportHistory.query
        .filter_by(user_id=user_id)
        .order_by(ReportHistory.generated_at.desc())
        .all()
    )

    return jsonify({
        "reports": [
            {
                "id": r.id,
                "case_id": r.case_id,
                "case_name": r.case_name,
                "report_type": r.report_type,
                "generated_at": r.generated_at.isoformat(),
            }
            for r in reports
        ]
    })


@reports_bp.route("/reports/<int:report_id>/download")
def download_report(report_id):
    """Download a generated PDF report."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    record = ReportHistory.query.filter_by(id=report_id, user_id=user_id).first()
    if not record:
        return jsonify({"error": "Report not found"}), 404

    reports_dir = os.path.join(current_app.root_path, "..", "generated_reports")
    file_path = os.path.join(reports_dir, record.file_path)

    if not os.path.exists(file_path):
        return jsonify({"error": "Report file not found on disk"}), 404

    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{record.case_name}_{record.report_type}.pdf",
    )
