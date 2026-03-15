import os

from flask import Flask, send_from_directory
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, migrate

# Path to the built React frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


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
    CORS(app, supports_credentials=True, origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://caseraft.com",
        "https://web-production-f49df.up.railway.app",
    ])

    # Blueprints
    from app.routes.auth import auth_bp
    from app.routes.cases import cases_bp
    from app.routes.reports import reports_bp
    from app.routes.billing import billing_bp
    from app.routes.contact import contact_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(cases_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    app.register_blueprint(contact_bp, url_prefix="/api")

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
