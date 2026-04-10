"""Shared pytest fixtures for Case Raft backend tests."""

import os

import pytest


@pytest.fixture
def app():
    """Build a Flask app configured for tests: in-memory sqlite, dev mode.

    Each test gets a fresh DB. Clio + Stripe env vars are stubbed so
    create_app() doesn't blow up during import.
    """
    os.environ["FLASK_ENV"] = "development"
    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ.setdefault("CLIO_CLIENT_ID", "test-client-id")
    os.environ.setdefault("CLIO_CLIENT_SECRET", "test-client-secret")
    os.environ.setdefault("CLIO_REDIRECT_URI", "http://localhost:5000/auth/callback")
    os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_stub")
    os.environ.setdefault("STRIPE_PUBLIC_KEY", "pk_test_stub")
    os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_stub")
    os.environ.setdefault("STRIPE_PRICE_SOLO", "price_solo_stub")
    os.environ.setdefault("STRIPE_PRICE_TEAM", "price_team_stub")
    os.environ.setdefault("STRIPE_PRICE_FIRM", "price_firm_stub")

    from app import create_app
    from app.extensions import db

    app = create_app()
    app.config["TESTING"] = True
    # Keep limits from tripping tests
    app.config["RATELIMIT_ENABLED"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    """Factory that creates and returns a User with the given tier/status."""
    from app.extensions import db
    from app.models.user import User

    def _factory(email="user@example.com", plan_tier="solo",
                 subscription_status="active"):
        user = User(
            email=email,
            clio_access_token="stub-access",
            clio_refresh_token="stub-refresh",
            plan_tier=plan_tier,
            subscription_status=subscription_status,
        )
        db.session.add(user)
        db.session.commit()
        return user

    return _factory
