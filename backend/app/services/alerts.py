"""Slack alert fanout for Case Raft.

Lightweight port of the Skybrook monitoring pattern. Lets the rest of the
codebase fire structured alerts to Slack without each call site knowing
about webhooks, channels, or formatting.

Configuration (env vars):
  SLACK_WEBHOOK_URL          — primary alerts channel (P0/P1/P2). Required
                               for the module to do anything.
  SLACK_WEBHOOK_SUPPORT_URL  — optional dedicated channel for support
                               inbound. Falls back to SLACK_WEBHOOK_URL.
  SLACK_MENTION_USER_IDS     — comma-separated Slack user IDs to @mention
                               on P0 (e.g. "U0B37DUSLUX"). Optional.

If SLACK_WEBHOOK_URL is unset, every `send_alert(...)` call is a silent
no-op — useful for dev/test environments where alerting would otherwise
spam a real channel. Tests can also blank these env vars in setUp to
guarantee isolation.
"""

import os
from typing import Iterable, Optional

import requests
from flask import current_app


# Severity → emoji + label. Block Kit will color-code via attachment color
# below. P0 is for "drop-everything"; P1 is for "fix today"; P2 is for
# "fix this week / informational"; P3 for debug-only signals.
_SEVERITY_META = {
    "p0": {"emoji": "🚨", "label": "P0 CRITICAL", "color": "#dc2626"},
    "p1": {"emoji": "⚠️", "label": "P1", "color": "#f97316"},
    "p2": {"emoji": "ℹ️", "label": "P2", "color": "#3b82f6"},
    "p3": {"emoji": "🔍", "label": "P3", "color": "#6b7280"},
    "support": {"emoji": "📨", "label": "Support", "color": "#10b981"},
}


def _logger():
    """Resolve a logger that works both inside and outside an app context."""
    try:
        return current_app.logger
    except RuntimeError:
        # No app context (e.g. import-time call) — fall back to stdlib.
        import logging
        return logging.getLogger("alerts")


def _webhook_for(severity: str) -> Optional[str]:
    """Pick the webhook URL for the given severity. Support messages route
    to SLACK_WEBHOOK_SUPPORT_URL if set; everything else routes to
    SLACK_WEBHOOK_URL."""
    if severity == "support":
        url = os.environ.get("SLACK_WEBHOOK_SUPPORT_URL")
        if url:
            return url
    return os.environ.get("SLACK_WEBHOOK_URL")


def _mention_prefix(severity: str) -> str:
    """Build a `<@U123> ...` mention prefix for P0 alerts. Empty string for
    other severities. Uses SLACK_MENTION_USER_IDS env var."""
    if severity != "p0":
        return ""
    user_ids = os.environ.get("SLACK_MENTION_USER_IDS", "").strip()
    if not user_ids:
        return ""
    mentions = " ".join(
        f"<@{uid.strip()}>" for uid in user_ids.split(",") if uid.strip()
    )
    return f"{mentions} " if mentions else ""


def send_alert(
    severity: str,
    title: str,
    body: str,
    *,
    fields: Optional[Iterable[tuple]] = None,
) -> bool:
    """Post a structured alert to Slack.

    Args:
        severity: "p0", "p1", "p2", "p3", or "support".
        title: Short headline (≤ 100 chars works best).
        body: Detail body, supports Slack mrkdwn. Keep ≤ 2000 chars.
        fields: Optional iterable of (label, value) pairs rendered as a
            two-column section after the body.

    Returns:
        True if the alert was POSTed (regardless of webhook response).
        False if there's no webhook configured (silent no-op).

    Failures (timeout, non-2xx) are logged but never re-raised — alerting
    is a best-effort secondary channel and should never crash the primary
    request path.
    """
    severity = severity.lower()
    meta = _SEVERITY_META.get(severity)
    if not meta:
        meta = _SEVERITY_META["p2"]
        severity = "p2"

    url = _webhook_for(severity)
    if not url:
        # Dev / test / un-configured environments: silent no-op.
        return False

    mention = _mention_prefix(severity)
    fallback_text = f"{mention}{meta['emoji']} *[{meta['label']}]* {title}"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{meta['emoji']} {meta['label']} — {title[:140]}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": body[:2900] if body else "_(no body)_",
            },
        },
    ]

    if fields:
        # Slack section "fields" max 10 entries × 2000 chars each.
        field_blocks = []
        for label, value in list(fields)[:10]:
            field_blocks.append(
                {"type": "mrkdwn", "text": f"*{label}*\n{str(value)[:1800]}"}
            )
        if field_blocks:
            blocks.append({"type": "section", "fields": field_blocks})

    payload = {
        "text": fallback_text,  # mention here triggers push for P0
        "attachments": [
            {"color": meta["color"], "blocks": blocks},
        ],
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code >= 400:
            _logger().warning(
                "slack alert returned %s for severity=%s title=%r",
                resp.status_code, severity, title,
            )
    except Exception as e:
        _logger().warning(
            "slack alert failed for severity=%s title=%r: %s",
            severity, title, e,
        )
    return True


# Convenience wrappers — keep call sites readable.

def alert_p0(title: str, body: str = "", **kwargs):
    return send_alert("p0", title, body, **kwargs)


def alert_p1(title: str, body: str = "", **kwargs):
    return send_alert("p1", title, body, **kwargs)


def alert_p2(title: str, body: str = "", **kwargs):
    return send_alert("p2", title, body, **kwargs)


def alert_support(title: str, body: str = "", **kwargs):
    return send_alert("support", title, body, **kwargs)
