import csv
import io
import os

from flask import Blueprint, Response, jsonify, request, send_file, session, current_app

from app.models.report_history import ReportHistory
from app.models.user import User
from app.services.clio_client import ClioAPIClient
from app.services.firm_data import FirmProductivityData
from app.services.report import CaseSummaryReport, FirmProductivityReport

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


@reports_bp.route("/reports/generate-batch", methods=["POST"])
def generate_batch_reports():
    """Generate PDF reports for multiple cases at once."""
    clio, user = _get_clio_client()
    if not clio:
        return jsonify({"error": "Not authenticated"}), 401

    sub_error = _require_subscription(user)
    if sub_error:
        return sub_error

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
            except Exception:
                pass

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

            report = CaseSummaryReport(
                case_data["data"], user.id,
                related_contacts=related_contacts,
                bills=bills,
                activities=activities,
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

    if not user.is_paid:
        return jsonify({
            "error": "Upgrade required",
            "message": "Firm productivity reports require a paid plan.",
            "upgrade": True,
        }), 403

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

    options = data.get("options", {})
    report = report_cls(firm_data, user.id, options=options)
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

    if not user.is_paid:
        return jsonify({
            "error": "Upgrade required",
            "message": "CSV export requires a paid plan.",
            "upgrade": True,
        }), 403

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
