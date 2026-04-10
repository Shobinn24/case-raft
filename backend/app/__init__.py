import json
import os
import traceback as tb

from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, migrate

# Path to the built React frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

# Keys to strip from logged request bodies
_SENSITIVE_KEYS = {"access_token", "refresh_token", "password", "secret", "token"}


def _sanitize_body(data):
    """Remove sensitive fields from request body before logging."""
    if not data:
        return None
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict):
            return json.dumps(
                {k: "***" if k.lower() in _SENSITIVE_KEYS else v for k, v in data.items()}
            )
        return str(data)[:2000]
    except Exception:
        return None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Trust proxy headers (ngrok/Railway -> Flask)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Fix SQLAlchemy URI for Railway (postgres:// -> postgresql://)
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri and uri.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace("postgres://", "postgresql://", 1)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Only allow dev origins in development
    allowed_origins = [
        "https://caseraft.com",
        "https://www.caseraft.com",
        "https://web-production-f49df.up.railway.app",
    ]
    if app.debug or os.environ.get("FLASK_ENV") == "development":
        allowed_origins += [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    CORS(app, supports_credentials=True, origins=allowed_origins)

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.cases import cases_bp
    from app.routes.reports import reports_bp
    from app.routes.billing import billing_bp
    from app.routes.contact import contact_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(cases_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    app.register_blueprint(contact_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # ---- Security headers ----
    @app.after_request
    def set_security_headers(response):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    # ---- Error logging middleware ----

    # Known bot/scanner paths — ignore these to keep logs clean
    _BOT_PATHS = {"/", "/index.php", "/wp-login.php", "/wp-admin",
                  "/.env", "/xmlrpc.php", "/config.php", "/robots.txt"}

    @app.after_request
    def log_errors(response):
        """Log 4xx and 5xx responses to the error_logs table."""
        if response.status_code < 400:
            return response
        # Skip if handle_exception already logged this 500 (prevents double-logging)
        if response.headers.pop("X-Error-Already-Logged", None):
            return response
        # Skip static file 404s and CORS preflight
        if request.method == "OPTIONS":
            return response
        if request.path.startswith("/assets/") or request.path.endswith((".js", ".css", ".ico", ".png", ".jpg")):
            return response
        # Skip bot/scanner noise (unauthenticated POST to common scan targets)
        if not session.get("user_id") and request.path in _BOT_PATHS:
            return response
        if request.path.endswith(".php"):
            return response

        try:
            from app.models.error_log import ErrorLog
            from app.models.user import User

            user_id = session.get("user_id")
            user_email = None
            if user_id:
                user = User.query.get(user_id)
                if user:
                    user_email = user.email

            # Extract error message from response
            error_message = ""
            try:
                resp_data = response.get_json(silent=True)
                if resp_data and isinstance(resp_data, dict):
                    error_message = resp_data.get("error", "")
                    if not error_message:
                        error_message = resp_data.get("message", "")
                if not error_message:
                    error_message = response.get_data(as_text=True)[:1000]
            except Exception:
                error_message = f"HTTP {response.status_code}"

            log_entry = ErrorLog(
                user_id=user_id,
                user_email=user_email,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                error_message=error_message,
                request_body=_sanitize_body(request.get_data()),
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception:
            db.session.rollback()  # Don't let logging errors break the app

        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Catch unhandled exceptions, log them, and return 500."""
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            # Let HTTP exceptions (404, 405, etc.) pass through normally.
            # They're already logged by the after_request handler above.
            return e
        try:
            from app.models.error_log import ErrorLog

            user_id = session.get("user_id")
            user_email = None
            if user_id:
                from app.models.user import User
                user = User.query.get(user_id)
                if user:
                    user_email = user.email

            log_entry = ErrorLog(
                user_id=user_id,
                user_email=user_email,
                endpoint=request.path,
                method=request.method,
                status_code=500,
                error_message=str(e)[:1000],
                request_body=_sanitize_body(request.get_data()),
                traceback=tb.format_exc(),
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception:
            db.session.rollback()

        app.logger.exception(f"Unhandled exception on {request.path}")
        response = jsonify({"error": "Internal server error"})
        response.status_code = 500
        # Flag so the after_request logger skips this (we already logged above)
        response.headers["X-Error-Already-Logged"] = "1"
        return response

    # Serve React frontend in production
    if os.path.isdir(FRONTEND_DIR):
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path):
            file_path = os.path.join(FRONTEND_DIR, path)
            if path and os.path.isfile(file_path):
                return send_from_directory(FRONTEND_DIR, path)
            return send_from_directory(FRONTEND_DIR, "index.html")

    return app
