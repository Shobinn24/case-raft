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
