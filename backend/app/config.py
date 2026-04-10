import os
from datetime import timedelta


_env = os.environ.get("FLASK_ENV", "production")
_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    if _env == "development":
        _secret_key = "dev-secret-change-me"
    else:
        raise RuntimeError(
            "SECRET_KEY environment variable is required in production"
        )


class Config:
    SECRET_KEY = _secret_key
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///caseraft.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") != "development"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_REFRESH_EACH_REQUEST = True

    # Clio OAuth
    CLIO_CLIENT_ID = os.environ.get("CLIO_CLIENT_ID")
    CLIO_CLIENT_SECRET = os.environ.get("CLIO_CLIENT_SECRET")
    CLIO_REDIRECT_URI = os.environ.get("CLIO_REDIRECT_URI")
    # Clio Manage endpoints (US region)
    CLIO_BASE_URL = "https://app.clio.com"
    CLIO_API_URL = "https://app.clio.com/api/v4"
    CLIO_AUTH_URL = "https://app.clio.com/oauth/authorize"
    CLIO_TOKEN_URL = "https://app.clio.com/oauth/token"

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_SOLO = os.environ.get("STRIPE_PRICE_SOLO")
    STRIPE_PRICE_TEAM = os.environ.get("STRIPE_PRICE_TEAM")
    STRIPE_PRICE_FIRM = os.environ.get("STRIPE_PRICE_FIRM")
    STRIPE_COUPON_ID = os.environ.get("STRIPE_COUPON_ID")
