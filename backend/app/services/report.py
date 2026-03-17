import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

from flask import current_app, render_template_string

from app.extensions import db
from app.models.report_history import ReportHistory
from app.services.case import Case

# Mapping of common Clio timezone names to UTC offsets (hours).
# Clio uses Rails-style timezone names (e.g., "Eastern Time (US & Canada)").
_TZ_OFFSETS = {
    "eastern time (us & canada)": -4,
    "central time (us & canada)": -5,
    "mountain time (us & canada)": -6,
    "pacific time (us & canada)": -7,
    "alaska": -8,
    "hawaii": -10,
    "atlantic time (canada)": -3,
    "arizona": -7,
    "indiana (east)": -4,
    "utc": 0,
    "london": 1,
}


def _get_tz(user_tz_name):
    """Return a timezone object from a Clio timezone name. Falls back to Eastern."""
    if user_tz_name:
        offset = _TZ_OFFSETS.get(user_tz_name.strip().lower())
        if offset is not None:
            return timezone(timedelta(hours=offset))
    # Default to Eastern if unknown
    return timezone(timedelta(hours=-4))


class Report(ABC):
    """Abstract base class for all report types."""

    REPORT_TYPE = "base"

    def __init__(self, case_data, user_id, related_contacts=None,
                 bills=None, activities=None, user_tz=None):
        self.case = Case(case_data)
        self.user_id = user_id
        tz = _get_tz(user_tz)
        self.generated_at = datetime.now(tz).strftime("%B %d, %Y at %I:%M %p")

        # Populate related contacts (opposing parties, counsel, court)
        if related_contacts:
            self.case.set_related_contacts(related_contacts)

        # Populate billing data
        if bills or activities:
            self.case.set_billing_data(bills or [], activities or [])

    @abstractmethod
    def _get_template(self):
        """Return the HTML template string for this report type."""

    def _render_html(self):
        """Render the HTML template with case data."""
        template = self._get_template()
        return render_template_string(template, case=self.case, generated_at=self.generated_at)

    def generate(self):
        """Generate the PDF, save to disk, and record in report history. Returns the ReportHistory record."""
        html_content = self._render_html()

        # Build output path
        reports_dir = os.path.join(current_app.root_path, "..", "generated_reports")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"{self.REPORT_TYPE}_{self.case.id}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(reports_dir, filename)

        # Generate PDF (lazy import — WeasyPrint loads heavy C libraries)
        from weasyprint import HTML
        HTML(string=html_content).write_pdf(file_path)

        # Record in history
        record = ReportHistory(
            user_id=self.user_id,
            case_id=self.case.id,
            case_name=self.case.title,
            report_type=self.REPORT_TYPE,
            file_path=filename,
        )
        db.session.add(record)
        db.session.commit()

        return record


class CaseSummaryReport(Report):
    """Generates a Case Summary PDF report."""

    REPORT_TYPE = "case_summary"

    def _get_template(self):
        template_path = os.path.join(
            current_app.root_path, "templates", "case_summary.html"
        )
        with open(template_path) as f:
            return f.read()


# ------------------------------------------------------------------
# Firm-wide reports (not tied to a specific case)
# ------------------------------------------------------------------

class FirmReport(ABC):
    """Abstract base class for firm-wide reports."""

    REPORT_TYPE = "firm_base"

    def __init__(self, firm_data, user_id, options=None, user_tz=None):
        self.firm_data = firm_data
        self.user_id = user_id
        self.options = options or {}
        tz = _get_tz(user_tz)
        self.generated_at = datetime.now(tz).strftime("%B %d, %Y at %I:%M %p")

    @abstractmethod
    def _get_template(self):
        """Return the HTML template string for this report type."""

    def _render_html(self):
        """Render the HTML template with firm data."""
        template = self._get_template()
        sections = self.options.get("sections", {})
        return render_template_string(
            template, data=self.firm_data, generated_at=self.generated_at,
            show=sections,
        )

    def generate(self):
        """Generate the PDF, save to disk, and record in report history."""
        html_content = self._render_html()

        reports_dir = os.path.join(current_app.root_path, "..", "generated_reports")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"{self.REPORT_TYPE}_{uuid.uuid4().hex[:8]}.pdf"
        file_path = os.path.join(reports_dir, filename)

        from weasyprint import HTML
        HTML(string=html_content).write_pdf(file_path)

        record = ReportHistory(
            user_id=self.user_id,
            case_id=None,
            case_name=self.firm_data.title,
            report_type=self.REPORT_TYPE,
            file_path=filename,
        )
        db.session.add(record)
        db.session.commit()

        return record


class FirmProductivityReport(FirmReport):
    """Generates a Firm Productivity PDF report."""

    REPORT_TYPE = "firm_productivity"

    def _get_template(self):
        template_path = os.path.join(
            current_app.root_path, "templates", "firm_productivity.html"
        )
        with open(template_path) as f:
            return f.read()


class RevenueByPracticeAreaReport(FirmReport):
    """Generates a Revenue by Practice Area PDF report."""

    REPORT_TYPE = "revenue_by_practice_area"

    def _get_template(self):
        template_path = os.path.join(
            current_app.root_path, "templates", "revenue_by_practice_area.html"
        )
        with open(template_path) as f:
            return f.read()


class TrustManagementReport(FirmReport):
    """Generates a Trust Management PDF report showing clients below trust threshold."""

    REPORT_TYPE = "trust_management"

    def _get_template(self):
        template_path = os.path.join(
            current_app.root_path, "templates", "trust_management.html"
        )
        with open(template_path) as f:
            return f.read()
