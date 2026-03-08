import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///caseraft.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session cookie settings — "None" + Secure allows cross-site OAuth redirects via ngrok
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True

    # Clio OAuth
    CLIO_CLIENT_ID = os.environ.get("CLIO_CLIENT_ID")
    CLIO_CLIENT_SECRET = os.environ.get("CLIO_CLIENT_SECRET")
    CLIO_REDIRECT_URI = os.environ.get("CLIO_REDIRECT_URI")
    # Clio Manage endpoints (US region)
    CLIO_BASE_URL = "https://app.clio.com"
    CLIO_API_URL = "https://app.clio.com/api/v4"
    CLIO_AUTH_URL = "https://app.clio.com/oauth/authorize"
    CLIO_TOKEN_URL = "https://app.clio.com/oauth/token"
