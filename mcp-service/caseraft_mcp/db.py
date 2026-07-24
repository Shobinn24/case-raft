"""Database access for the MCP service.

Maps the EXISTING `users` table (the columns this service needs, read-write:
Clio token refresh writes rotated tokens back exactly like the Flask path)
plus the three new MCP tables. Schema for the new tables is owned by the
Flask app's Alembic migrations; this module never creates tables in
production (tests call create_all against sqlite).

Concurrency model: one engine per process (lazily built, rebuilt if
DATABASE_URL changes, which only happens in tests), one short-lived session
per unit of work via session_scope(). No module-level session, so multiple
uvicorn workers are safe.
"""

import os
import uuid
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings
from .crypto import EncryptedText


class Base(DeclarativeBase):
    pass


def _new_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Existing table (subset of columns; the Flask app owns the full model)
# ---------------------------------------------------------------------------

# Whitelist/admin defaults mirror backend/app/models/user.py exactly so the
# subscription gate behaves identically in both services.

def _env_set(name, default):
    raw = os.environ.get(name, default)
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


_DEFAULT_WHITELISTED_DOMAINS = "trustice.us"
_DEFAULT_WHITELISTED_EMAILS = "srhoades@trustice.us,shobinn24@gmail.com,shobinn@eclarx.com"
_DEFAULT_ADMIN_EMAILS = "shobinn24@gmail.com"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    clio_access_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    clio_refresh_token: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String(50), default="free")
    plan_tier: Mapped[str | None] = mapped_column(String(50), default="free")
    is_admin: Mapped[bool | None] = mapped_column(Boolean, default=False)
    # Rails-style zone name from Clio, e.g. "Eastern Time (US & Canada)"
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    WHITELISTED_DOMAINS = _env_set("WHITELISTED_DOMAINS", _DEFAULT_WHITELISTED_DOMAINS)
    WHITELISTED_EMAILS = _env_set("WHITELISTED_EMAILS", _DEFAULT_WHITELISTED_EMAILS)
    ADMIN_EMAILS = _env_set("ADMIN_EMAILS", _DEFAULT_ADMIN_EMAILS)

    @property
    def check_is_admin(self):
        if not self.email:
            return False
        return self.email.lower() in self.ADMIN_EMAILS or bool(self.is_admin)

    @property
    def is_whitelisted(self):
        if not self.email:
            return False
        email_lower = self.email.lower()
        if email_lower in self.WHITELISTED_EMAILS:
            return True
        domain = email_lower.split("@")[-1]
        return domain in self.WHITELISTED_DOMAINS

    @property
    def is_paid(self):
        if self.check_is_admin or self.is_whitelisted:
            return True
        return self.subscription_status == "active" and self.plan_tier != "free"


# ---------------------------------------------------------------------------
# New MCP tables (created by the Flask migration; mirrored here)
# ---------------------------------------------------------------------------

class MCPClient(Base):
    __tablename__ = "mcp_clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    client_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_uris: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MCPAuthCode(Base):
    __tablename__ = "mcp_auth_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    code_challenge: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    redirect_uri: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MCPToken(Base):
    __tablename__ = "mcp_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    refresh_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Mirror of the Flask app's audit_logs table (backend/app/models/
    audit_log.py). Insert-only; every MCP tool call writes one row via
    caseraft_mcp.audit.record_audit."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    user_email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Engine / session management
# ---------------------------------------------------------------------------

_engine = None
_engine_url = None


def get_engine():
    """Process-local engine, rebuilt if DATABASE_URL changes (test isolation)."""
    global _engine, _engine_url
    url = settings.database_url
    if _engine is None or _engine_url != url:
        if _engine is not None:
            _engine.dispose()
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs = {"connect_args": {"check_same_thread": False}}
        _engine = create_engine(url, **kwargs)
        _engine_url = url
    return _engine


def reset_engine():
    """Drop the cached engine (tests)."""
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None


@contextmanager
def session_scope():
    """One transactional session per unit of work. Commits on success,
    rolls back on error, always closes."""
    session = sessionmaker(bind=get_engine(), expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_all():
    """Create tables (tests only; production schema comes from Flask Alembic)."""
    Base.metadata.create_all(get_engine())
