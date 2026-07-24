"""Environment configuration for the CaseRaft MCP service.

This service is deliberately self-contained: it never imports the Flask app.
It talks to the same Postgres database and shares only environment contracts:

  DATABASE_URL          same database the Flask app uses. Railway hands out
                        "postgres://" URLs; SQLAlchemy wants "postgresql://",
                        so we apply the same fixup app/__init__.py does.
  TOKEN_ENCRYPTION_KEY  Fernet key for Clio tokens at rest (same key as Flask).
  CLIO_CLIENT_ID        Clio OAuth app credentials, needed to refresh a user's
  CLIO_CLIENT_SECRET    Clio access token mid-request.
  CLIO_TOKEN_URL        Clio token endpoint (default: production US region).
  CLIO_API_URL          Clio Manage API v4 base URL.
  MCP_ISSUER_URL        Public base URL of THIS service. Default
                        https://mcp.caseraft.com
  CONSENT_URL           The Flask consent page that /authorize redirects the
                        browser to. Default https://caseraft.com/connect/authorize

Canonical MCP URL
-----------------
The canonical URL users paste into Claude is exactly:

    https://mcp.caseraft.com/mcp

(no trailing slash). The protected-resource metadata `resource` field equals
this string exactly, and it is the only form we publish anywhere. Per the
Phase 0 findings, Claude matches the metadata `resource` against the URL as
typed, so docs, the onboarding page, and the connectors-directory listing must
all use this exact form.

Settings are read from the environment on attribute access (not at import
time) so tests can set variables before or after import.
"""

import os


def _fix_database_url(url):
    """Railway-style postgres:// URLs -> postgresql:// (same fixup as Flask)."""
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Settings:
    @property
    def database_url(self):
        return _fix_database_url(
            os.environ.get("DATABASE_URL", "sqlite:///caseraft_mcp_dev.db")
        )

    @property
    def token_encryption_key(self):
        return os.environ.get("TOKEN_ENCRYPTION_KEY")

    @property
    def clio_client_id(self):
        return os.environ.get("CLIO_CLIENT_ID")

    @property
    def clio_client_secret(self):
        return os.environ.get("CLIO_CLIENT_SECRET")

    @property
    def clio_token_url(self):
        return os.environ.get("CLIO_TOKEN_URL", "https://app.clio.com/oauth/token")

    @property
    def clio_api_url(self):
        return os.environ.get("CLIO_API_URL", "https://app.clio.com/api/v4")

    @property
    def mcp_issuer_url(self):
        return os.environ.get("MCP_ISSUER_URL", "https://mcp.caseraft.com").rstrip("/")

    @property
    def consent_url(self):
        return os.environ.get("CONSENT_URL", "https://caseraft.com/connect/authorize")

    @property
    def canonical_mcp_url(self):
        """The exact URL users configure in Claude; also the RFC 8707 resource."""
        return f"{self.mcp_issuer_url}/mcp"

    @property
    def resource_metadata_url(self):
        """Value advertised in WWW-Authenticate on 401s (Phase 0 finding:
        Claude only honors this header on 401 responses)."""
        return f"{self.mcp_issuer_url}/.well-known/oauth-protected-resource"

    # Token lifetimes (seconds). Auth codes are short-lived single-use;
    # access tokens rotate hourly; refresh tokens live until rotated/revoked.
    @property
    def auth_code_ttl(self):
        return int(os.environ.get("MCP_AUTH_CODE_TTL", "600"))

    @property
    def access_token_ttl(self):
        return int(os.environ.get("MCP_ACCESS_TOKEN_TTL", "3600"))


settings = Settings()
