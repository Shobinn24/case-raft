"""Tests for /api/health detailed readiness endpoint.

The simple /health stays a flat 200 (Railway liveness). /api/health
returns 200 with structured check details, or 503 if any check fails.
Healthchecks.io polls /api/health every 10 min.
"""

from unittest.mock import patch


def test_health_liveness_always_200(client):
    """Simple /health stays flat — never 503. Railway depends on this for
    container liveness."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "ok"


def test_api_health_returns_200_when_db_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["service"] == "caseraft"
    assert "asOf" in data

    # DB check should be present and pass
    db_check = next(c for c in data["checks"] if c["name"] == "db")
    assert db_check["status"] == "pass"


def test_api_health_includes_stripe_webhook_check(client):
    resp = client.get("/api/health")
    data = resp.get_json()
    sw = next(c for c in data["checks"] if c["name"] == "stripe_webhooks")
    # No events written in test DB → pass with informational detail
    assert sw["status"] == "pass"
    assert "no events yet" in sw["detail"].lower()


def test_api_health_503_when_db_unreachable(client):
    """Simulate a DB failure — endpoint must 503 so healthchecks.io alerts."""
    with patch(
        "app.extensions.db.session.execute",
        side_effect=Exception("connection refused"),
    ):
        resp = client.get("/api/health")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["ok"] is False
    db_check = next(c for c in data["checks"] if c["name"] == "db")
    assert db_check["status"] == "fail"
