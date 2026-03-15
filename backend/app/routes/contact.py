import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.contact_message import ContactMessage

contact_bp = Blueprint("contact", __name__)

CONTACT_EMAIL = "shobinn@eclarx.com"


@contact_bp.route("/contact", methods=["POST"])
def submit_contact():
    """Handle contact form submissions — store in DB and send email."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    firm_name = (data.get("firm_name") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Name, email, and message are required"}), 400

    # Store in database
    msg = ContactMessage(
        name=name,
        email=email,
        firm_name=firm_name or None,
        message=message,
    )
    db.session.add(msg)
    db.session.commit()

    # Send email notification
    try:
        _send_notification_email(name, email, firm_name, message)
    except Exception:
        pass  # Don't fail the request if email fails — message is saved in DB

    return jsonify({"message": "Thank you! We'll be in touch soon."}), 201


def _send_notification_email(name, email, firm_name, message):
    """Send an email notification for a new contact form submission."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_host, smtp_user, smtp_pass]):
        return  # Email not configured — skip silently

    subject = f"CaseRaft Contact: {name}"
    if firm_name:
        subject += f" ({firm_name})"

    body = f"""New contact form submission from CaseRaft:

Name: {name}
Email: {email}
Firm: {firm_name or 'Not provided'}

Message:
{message}

---
Submitted at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
"""

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = CONTACT_EMAIL
    msg["Reply-To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
