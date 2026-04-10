import csv
import io
import os

from flask import Blueprint, Response, jsonify, request, send_file, session, current_app

from app.models.report_history import ReportHistory
from app.models.user import User
from app.services.clio_client import ClioAPIClient
from app.services.firm_data import FirmProductivityData, RevenueByPracticeAreaData, TrustManagementData
from app.services.report import (
    CaseSummaryReport, FirmProductivityReport,
    RevenueByPracticeAreaReport, TrustManagementReport,
)

reports_bp = Blueprint("reports", __name__)

def _require_subscription(user):
    """Ensure the user has an active paid subscription."""
    if not user.is_paid:
        return jsonify({
            "error": "Subscription required",
            "message": "An active subscription is required to use this feature. Please choose a plan.",
            "upgrade": True,
        }), 403
    return None


# Tiers that include analytics / trust management features
_ANALYTICS_TIERS = {"team", "firm"}


def _require_tier(user, allowed_tiers, feature_name="This feature"):
    """Ensure the user's plan tier is in the allowed set."""
    sub_err = _require_subscription(user)
    if sub_err:
        return sub_err
    if user.effective_plan_tier not in allowed_tiers:
        return jsonify({
            "error": "Plan upgrade required",
            "message": f"{feature_name} requires a Team or Firm plan.",
            "upgrade": True,
        }), 403
    return None


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

    # Subscription check
    sub_error = _require_subscription(user)
    if sub_error:
        return sub_error

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
    except Exception as e:
        current_app.logger.warning(
            f"Failed to fetch related_contacts for case {case_id}: {e}"
        )  # Non-critical — report still works without relationships

    # Fetch billing data (invoices and time entries)
    bills = []
    activities = []
    try:
        bills_resp = clio.get_bills(case_id)
        bills = bills_resp.get("data", [])
    except Exception as e:
        current_app.logger.warning(
            f"Failed to fetch bills for case {case_id}: {e}"
        )
    try:
        activities_resp = clio.get_activities(case_id)
        activities = activities_resp.get("data", [])
    except Exception as e:
        current_app.logger.warning(
            f"Failed to fetch activities for case {case_id}: {e}"
        )

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
        user_tz=user.timezone,
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


@reports_bp.route("/reports/generate-batch", methods=["POST"])
def generate_batch_reports():
    """Generate PDF reports for multiple cases at once."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    tier_error = _require_tier(user, _ANALYTICS_TIERS, "Batch report generation")
    if tier_error:
        return tier_error

    data = request.get_json()
    case_ids = data.get("case_ids", []) if data else []
    if not case_ids:
        return jsonify({"error": "case_ids array is required"}), 400
    if len(case_ids) > 20:
        return jsonify({"error": "Maximum 20 cases per batch"}), 400

    reports = []
    errors = []

    for case_id in case_ids:
        try:
            case_data = clio.get_matter(case_id)
            if "data" not in case_data:
                errors.append({"case_id": case_id, "error": "Failed to fetch"})
                continue

            related_contacts = []
            try:
                rc_resp = clio.get_related_contacts(case_id)
                related_contacts = rc_resp.get("data", [])
            except Exception as e:
                current_app.logger.warning(
                    f"[batch] Failed to fetch related_contacts for case {case_id}: {e}"
                )

            bills = []
            activities = []
            try:
                bills_resp = clio.get_bills(case_id)
                bills = bills_resp.get("data", [])
            except Exception as e:
                current_app.logger.warning(
                    f"[batch] Failed to fetch bills for case {case_id}: {e}"
                )
            try:
                activities_resp = clio.get_activities(case_id)
                activities = activities_resp.get("data", [])
            except Exception as e:
                current_app.logger.warning(
                    f"[batch] Failed to fetch activities for case {case_id}: {e}"
                )

            report = CaseSummaryReport(
                case_data["data"], user.id,
                related_contacts=related_contacts,
                bills=bills,
                activities=activities,
                user_tz=user.timezone,
            )
            record = report.generate()
            reports.append({
                "id": record.id,
                "case_id": record.case_id,
                "case_name": record.case_name,
                "report_type": record.report_type,
                "generated_at": record.generated_at.isoformat(),
            })
        except Exception as e:
            errors.append({"case_id": case_id, "error": str(e)})

    return jsonify({
        "message": f"{len(reports)} report(s) generated",
        "reports": reports,
        "errors": errors,
    })


@reports_bp.route("/reports/generate-firm", methods=["POST"])
def generate_firm_report():
    """Generate a firm-wide PDF report for a given date range."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    sub_error = _require_subscription(user)
    if sub_error:
        return sub_error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    report_type = data.get("report_type", "firm_productivity")
    options = data.get("options", {})

    # Team+ gating for analytics reports
    if report_type == "firm_productivity":
        tier_error = _require_tier(user, _ANALYTICS_TIERS, "Firm productivity report")
        if tier_error:
            return tier_error
    elif report_type == "revenue_by_practice_area":
        tier_error = _require_tier(user, _ANALYTICS_TIERS, "Revenue by practice area report")
        if tier_error:
            return tier_error

    # Trust Management Report — restricted to whitelisted tester only
    _TRUST_ALLOWED_EMAILS = {"srhoades@trustice.us"}
    if report_type == "trust_management":
        if user.email.lower() not in _TRUST_ALLOWED_EMAILS:
            return jsonify({"error": "Trust Management Report is not currently available."}), 403
        try:
            matters_data = clio.get_matters_with_trust_data()
        except Exception as e:
            return jsonify({"error": f"Failed to fetch matters: {str(e)}"}), 502

        trust_data = TrustManagementData(matters_data)
        report = TrustManagementReport(trust_data, user.id, options=options, user_tz=user.timezone)
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

    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400

    # Revenue by Practice Area only needs bills + practice area names
    if report_type == "revenue_by_practice_area":
        try:
            bills_data = clio.get_all_bills_simple(start_date, end_date)
        except Exception as e:
            return jsonify({"error": f"Failed to fetch bills: {str(e)}"}), 502

        # Fetch practice areas for id->name lookup (second-level nests
        # only return default fields like id, not name)
        pa_lookup = {}
        try:
            pa_resp = clio.get_practice_areas()
            for pa in pa_resp.get("data", []):
                pa_lookup[pa["id"]] = pa.get("name", "Unknown")
        except Exception as e:
            current_app.logger.warning(
                f"Failed to fetch practice_areas for revenue report: {e}"
            )  # Report still works — practice areas show as "Uncategorized"

        mode = options.get("mode", "collected")
        rev_data = RevenueByPracticeAreaData(
            start_date, end_date, bills_data, mode=mode,
            practice_area_lookup=pa_lookup,
        )
        report = RevenueByPracticeAreaReport(rev_data, user.id, options=options, user_tz=user.timezone)
        record = report.generate()
    else:
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

        # Fetch practice areas for id->name lookup
        pa_lookup = {}
        try:
            pa_resp = clio.get_practice_areas()
            for pa in pa_resp.get("data", []):
                pa_lookup[pa["id"]] = pa.get("name", "Unknown")
        except Exception as e:
            current_app.logger.warning(
                f"Failed to fetch practice_areas for firm productivity report: {e}"
            )

        # Build full firm data model for productivity reports
        firm_data = FirmProductivityData(
            start_date, end_date, users_data, activities_data, bills_data,
            practice_area_lookup=pa_lookup,
        )
        firm_report_classes = {
            "firm_productivity": FirmProductivityReport,
        }
        report_cls = firm_report_classes.get(report_type)
        if not report_cls:
            return jsonify({"error": f"Unknown report type: {report_type}"}), 400

        report = report_cls(firm_data, user.id, options=options, user_tz=user.timezone)
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


@reports_bp.route("/reports/export-accounting", methods=["POST"])
def export_accounting():
    """Export firm billing data as CSV for QuickBooks or Xero import."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    tier_error = _require_tier(user, _ANALYTICS_TIERS, "Accounting CSV export")
    if tier_error:
        return tier_error

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    start_date = data.get("start_date")
    end_date = data.get("end_date")
    export_format = data.get("format", "quickbooks")

    if not start_date or not end_date:
        return jsonify({"error": "start_date and end_date are required"}), 400

    try:
        bills_data = clio.get_all_bills(start_date, end_date)
    except Exception as e:
        return jsonify({"error": f"Failed to fetch bills: {str(e)}"}), 502

    output = io.StringIO()
    writer = csv.writer(output)

    if export_format == "xero":
        writer.writerow([
            "*ContactName", "*InvoiceNumber", "*InvoiceDate", "*DueDate",
            "Total", "AmountPaid", "Status", "Description",
        ])
        for bill in bills_data:
            writer.writerow([
                bill.get("subject", ""),
                bill.get("number", ""),
                (bill.get("issued_at") or "")[:10],
                (bill.get("due_at") or "")[:10],
                f"{bill.get('total', 0):.2f}",
                f"{bill.get('paid', 0):.2f}",
                bill.get("state", ""),
                f"Invoice #{bill.get('number', '')}",
            ])
    else:  # quickbooks
        writer.writerow([
            "Date", "Transaction Type", "Name", "Account",
            "Debit", "Credit", "Memo", "Invoice #",
        ])
        for bill in bills_data:
            writer.writerow([
                (bill.get("issued_at") or "")[:10],
                "Invoice",
                bill.get("subject", ""),
                "Accounts Receivable",
                f"{bill.get('total', 0):.2f}",
                "",
                f"Invoice #{bill.get('number', '')}",
                bill.get("number", ""),
            ])
        # Payment rows for paid bills
        for bill in bills_data:
            if bill.get("state") == "paid" and bill.get("paid_at"):
                writer.writerow([
                    bill["paid_at"][:10],
                    "Payment",
                    bill.get("subject", ""),
                    "Accounts Receivable",
                    "",
                    f"{bill.get('paid', 0):.2f}",
                    f"Payment for Invoice #{bill.get('number', '')}",
                    bill.get("number", ""),
                ])

    csv_content = output.getvalue()
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename=accounting_export_{start_date}_{end_date}.csv"
        },
    )
