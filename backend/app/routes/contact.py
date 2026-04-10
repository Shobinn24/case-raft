import requests as http_requests
from flask import Blueprint, current_app, jsonify, request

from app.extensions import db, limiter
from app.models.contact_message import ContactMessage

contact_bp = Blueprint("contact", __name__)

FORMSPREE_URL = "https://formspree.io/f/xkoqrpjn"


@contact_bp.route("/contact", methods=["POST"])
@limiter.limit("5 per minute")
def submit_contact():
    """Handle contact form submissions — store in DB and forward to Formspree."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    name = (data.get("name") or "").strip()[:255]
    email = (data.get("email") or "").strip()[:255]
    firm_name = (data.get("firm_name") or "").strip()[:255]
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Name, email, and message are required"}), 400

    if len(message) > 10000:
        return jsonify({"error": "Message too long (max 10,000 characters)"}), 400

    # Basic email format check — not comprehensive, just a sanity filter
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Invalid email format"}), 400

    # Store in database
    msg = ContactMessage(
        name=name,
        email=email,
        firm_name=firm_name or None,
        message=message,
    )
    db.session.add(msg)
    db.session.commit()

    # Forward to Formspree for email notification
    try:
        http_requests.post(FORMSPREE_URL, json={
            "name": name,
            "email": email,
            "_replyto": email,
            "firm_name": firm_name or "Not provided",
            "message": message,
            "_subject": f"CaseRaft Contact: {name}" + (f" ({firm_name})" if firm_name else ""),
        }, timeout=10)
    except Exception:
        pass  # Don't fail the request if Formspree fails — message is saved in DB

    return jsonify({"message": "Thank you! We'll be in touch soon."}), 201
