"""Tests for the Slack alert module.

The module is a fire-and-forget wrapper around requests.post — these tests
verify:
  - Without SLACK_WEBHOOK_URL set, send_alert() is a silent no-op (no
    exception, no network call).
  - With the env var set, the POST is made with the expected payload
    shape (severity-coded color, headline, body, fields).
  - Failures in requests.post never re-raise out of send_alert (it's an
    auxiliary channel — should never crash the request path).
  - Severity routing: 'support' uses SLACK_WEBHOOK_SUPPORT_URL if set,
    falls back to SLACK_WEBHOOK_URL.
  - P0 prepends @mentions from SLACK_MENTION_USER_IDS.
"""

from unittest.mock import patch

import pytest

from app.services.alerts import send_alert, alert_p0, alert_p1, alert_support


def test_no_op_when_webhook_unset(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_SUPPORT_URL", raising=False)

    with patch("app.services.alerts.requests.post") as post:
        result = send_alert("p1", "ignored", "ignored")

    assert result is False
    assert post.call_count == 0


def test_p1_posts_to_main_webhook(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test-main")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            result = send_alert("p1", "Test failure", "Detail body")

    assert result is True
    assert post.call_count == 1
    call = post.call_args
    url = call.args[0] if call.args else call.kwargs.get("url")
    payload = call.kwargs.get("json") or call.args[1]
    assert url == "https://hooks.slack.com/test-main"
    # Headline is in the fallback text + the header block
    assert "P1" in payload["text"]
    assert "Test failure" in payload["text"]
    # Color encodes severity for visual scan-ability
    assert payload["attachments"][0]["color"] == "#f97316"


def test_p0_prefixes_mention(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test-main")
    monkeypatch.setenv("SLACK_MENTION_USER_IDS", "U123,U456")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            alert_p0("hot path down", "details")

    payload = post.call_args.kwargs["json"]
    # Both user IDs end up in the fallback text — that's what drives push
    # notifications on Slack
    assert "<@U123>" in payload["text"]
    assert "<@U456>" in payload["text"]


def test_p1_does_not_mention(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test-main")
    monkeypatch.setenv("SLACK_MENTION_USER_IDS", "U123")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            alert_p1("noisy but not urgent")

    payload = post.call_args.kwargs["json"]
    assert "<@U123>" not in payload["text"]


def test_support_uses_support_webhook_when_set(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/main")
    monkeypatch.setenv("SLACK_WEBHOOK_SUPPORT_URL", "https://hooks.slack.com/support-only")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            alert_support("New inbound", "from a user")

    call_url = post.call_args.args[0] if post.call_args.args else post.call_args.kwargs.get("url")
    assert call_url == "https://hooks.slack.com/support-only"


def test_support_falls_back_to_main_webhook(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/main")
    monkeypatch.delenv("SLACK_WEBHOOK_SUPPORT_URL", raising=False)

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            alert_support("New inbound", "from a user")

    call_url = post.call_args.args[0] if post.call_args.args else post.call_args.kwargs.get("url")
    assert call_url == "https://hooks.slack.com/main"


def test_failure_in_requests_does_not_raise(monkeypatch, app):
    """Slack outage / network blip must not crash the request path."""
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test-main")

    with patch(
        "app.services.alerts.requests.post",
        side_effect=Exception("connection refused"),
    ):
        with app.app_context():
            # Should not raise
            result = send_alert("p1", "test", "test")

    assert result is True  # returned True since URL was set — but POST failed silently


def test_fields_render_into_payload(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/main")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            send_alert(
                "p1",
                "Test",
                "Body",
                fields=[("Name", "Alice"), ("Email", "alice@example.com")],
            )

    payload = post.call_args.kwargs["json"]
    # Section with fields = the 3rd block (header, body, fields)
    blocks = payload["attachments"][0]["blocks"]
    field_block = next(b for b in blocks if b.get("type") == "section" and "fields" in b)
    rendered = " ".join(f["text"] for f in field_block["fields"])
    assert "Alice" in rendered
    assert "alice@example.com" in rendered


def test_unknown_severity_defaults_to_p2(monkeypatch, app):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/main")

    with patch("app.services.alerts.requests.post") as post:
        with app.app_context():
            send_alert("urgent", "Test", "Body")  # 'urgent' isn't a valid severity

    payload = post.call_args.kwargs["json"]
    assert "P2" in payload["text"]
