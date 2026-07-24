"""Audit logging for MCP tool calls, modeled on the Flask app's
app/services/audit.py: append-only, best-effort, NEVER raises into the tool
call. Rows land in the same audit_logs table the Flask app reads.

Detail strings must not contain client PII: log argument SHAPES (limits,
statuses, date ranges, id references, query lengths), never contact names,
search text, or matter descriptions.
"""

import logging

from .db import AuditLog, session_scope

logger = logging.getLogger(__name__)


def summarize_args(args):
    """Render a compact 'k=v k=v' summary from a dict, skipping Nones.
    Callers are responsible for only passing non-PII values."""
    parts = []
    for key, value in (args or {}).items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)


def record_audit(action, *, user_id=None, user_email=None, resource_type=None,
                 resource_id=None, detail=None):
    """Write one audit row. Failures are logged and swallowed."""
    try:
        with session_scope() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    user_email=user_email,
                    action=action,
                    resource_type=resource_type,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    detail=(detail[:500] if isinstance(detail, str) else detail),
                    ip_address=None,   # server-to-server from Anthropic infra
                    user_agent="caseraft-mcp",
                )
            )
        return True
    except Exception:  # pragma: no cover - audit must never break the tool
        logger.exception("audit log write failed: action=%s", action)
        return False
