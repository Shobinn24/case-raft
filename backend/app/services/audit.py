"""Append-only audit logging.

record_audit() captures who did what, from where, and when. It NEVER raises
into the caller — an audit-write failure must not break the user-facing
request, so all errors are swallowed (and logged). Call it AFTER the request's
own db.session.commit() so its commit doesn't flush unrelated pending writes.
"""

import logging

from flask import has_request_context, request

from app.extensions import db
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def record_audit(action, *, user=None, user_email=None, resource_type=None,
                 resource_id=None, detail=None):
    """Write one audit row. Best-effort: failures are logged, never raised."""
    try:
        ip = None
        ua = None
        if has_request_context():
            ip = request.remote_addr  # real client IP via ProxyFix (x_for=1)
            ua = (request.headers.get("User-Agent") or "")[:500] or None

        email = user_email or (getattr(user, "email", None) if user is not None else None)
        uid = getattr(user, "id", None) if user is not None else None

        entry = AuditLog(
            user_id=uid,
            user_email=email,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            detail=(detail[:500] if isinstance(detail, str) else detail),
            ip_address=ip,
            user_agent=ua,
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    except Exception:  # pragma: no cover - audit must never break the request
        logger.exception("audit log write failed: action=%s", action)
        try:
            db.session.rollback()
        except Exception:
            pass
        return None
