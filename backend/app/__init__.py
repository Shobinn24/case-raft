import json
import os
import traceback as tb

from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, migrate, limiter

# Path to the built React frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")

# Keys to strip from logged request bodies
_SENSITIVE_KEYS = {"access_token", "refresh_token", "password", "secret", "token"}


def _sanitize_recursive(obj):
    """Walk a dict/list structure and mask any key matching _SENSITIVE_KEYS."""
    if isinstance(obj, dict):
        return {
            k: "***" if k.lower() in _SENSITIVE_KEYS else _sanitize_recursive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_sanitize_recursive(item) for item in obj]
    return obj


def _sanitize_body(data):
    """Remove sensitive fields from request body before logging."""
    if not data:
        return None
    try:
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                return str(data)[:2000]
        return json.dumps(_sanitize_recursive(data))
    except Exception:
        return None


def _init_sentry():
    """Initialize Sentry error tracking if SENTRY_DSN is configured.

    Idempotent — Sentry SDK guards against double-init internally, but
    we also gate on the env var so dev/test/un-configured environments
    silently skip. Failure to import sentry_sdk (e.g. it's not in the
    install) is also non-fatal.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration(), SqlalchemyIntegration()],
            # Performance monitoring at a low sample rate to keep the free
            # tier within budget. Bump to 1.0 temporarily to debug a
            # specific perf regression.
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
            environment=os.environ.get("FLASK_ENV", "production"),
            release=os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
            send_default_pii=False,
        )
    except ImportError:
        # sentry_sdk not installed — silently skip rather than crashing the
        # whole app. The error-tracking workstream is non-essential to the
        # request path.
        pass


def create_app():
    # Sentry needs to be initialized BEFORE Flask + extensions so its
    # integrations can hook into the right layers.
    _init_sentry()

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
    limiter.init_app(app)

    # CORS origins — env var overrides hardcoded defaults
    default_origins = [
        "https://caseraft.com",
        "https://www.caseraft.com",
        "https://web-production-f49df.up.railway.app",
    ]
    env_origins = os.environ.get("CORS_ORIGINS", "")
    allowed_origins = (
        [o.strip() for o in env_origins.split(",") if o.strip()]
        if env_origins
        else default_origins
    )
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

    # Health check endpoint for Railway / uptime monitoring.
    # `/health` is the cheap liveness check (Railway uses it to decide if the
    # container is alive — returns 200 as long as Flask itself is running).
    # `/api/health` is the deeper readiness check (DB connectivity + freshness
    # signals). Healthchecks.io dead-man polls /api/health every 10 minutes
    # and alerts to Slack on miss or non-2xx.
    @app.route("/health")
    def health_check():
        return {"status": "ok", "service": "caseraft"}, 200

    @app.route("/api/health")
    def api_health():
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import text

        from app.models.stripe_webhook_event import StripeWebhookEvent

        checks = []
        overall_ok = True

        # 1) DB connectivity — cheap roundtrip.
        try:
            db.session.execute(text("SELECT 1"))
            checks.append({"name": "db", "status": "pass"})
        except Exception as e:
            checks.append({
                "name": "db",
                "status": "fail",
                "detail": f"{type(e).__name__}: {str(e)[:120]}",
            })
            overall_ok = False

        # 2) Most recent Stripe webhook timestamp — informational. A long
        # gap (no webhooks for 7+ days) can indicate a misconfigured
        # webhook URL on the Stripe side, but isn't an automatic fail
        # because a dev/staging env may legitimately have no traffic.
        try:
            latest = (
                db.session.query(StripeWebhookEvent)
                .order_by(StripeWebhookEvent.processed_at.desc())
                .first()
            )
            if latest is None:
                checks.append({
                    "name": "stripe_webhooks",
                    "status": "pass",
                    "detail": "no events yet (pre-launch / dev env)",
                })
            else:
                processed = latest.processed_at
                if processed.tzinfo is None:
                    processed = processed.replace(tzinfo=timezone.utc)
                age_days = (
                    datetime.now(timezone.utc) - processed
                ).total_seconds() / 86400
                check = {
                    "name": "stripe_webhooks",
                    "status": "pass",
                    "lastEventAt": processed.isoformat(),
                    "ageDays": round(age_days, 2),
                }
                if age_days > 7:
                    # Soft warning — informational, doesn't flip overall.
                    check["warning"] = "no Stripe webhook events in 7+ days"
                checks.append(check)
        except Exception as e:
            checks.append({
                "name": "stripe_webhooks",
                "status": "fail",
                "detail": f"{type(e).__name__}: {str(e)[:120]}",
            })
            overall_ok = False

        return jsonify({
            "ok": overall_ok,
            "service": "caseraft",
            "checks": checks,
            "asOf": datetime.now(timezone.utc).isoformat(),
        }), (200 if overall_ok else 503)

    # Serve React frontend in production
    if os.path.isdir(FRONTEND_DIR):
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path):
            # send_from_directory has built-in safe_join — no manual path handling
            if path:
                try:
                    return send_from_directory(FRONTEND_DIR, path)
                except Exception:
                    pass
            return send_from_directory(FRONTEND_DIR, "index.html")

    return app
