"""Shared pytest fixtures for Case Raft backend tests."""

import os

import pytest


# Test env must be set BEFORE any test module is imported. Three test files
# (test_alerts.py, test_revenue_math.py, test_webhook_handlers.py) import from
# app.services.* at module top, which transitively triggers app/config.py and
# requires SECRET_KEY / DATABASE_URL / Clio / Stripe to be present at import
# time. Pytest imports conftest.py before collecting any sibling test module,
# so module-level assignment here is the earliest hook available — fixture-
# level assignment runs too late and the affected files fail with collection
# errors on a clean shell. All values are forced (not setdefault) so a
# polluted shell env (e.g. STRIPE_PRICE_TEAM=p2 leaking from a prior session)
# can't make a hardcoded-stub test fail.
os.environ["FLASK_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CLIO_CLIENT_ID"] = "test-client-id"
os.environ["CLIO_CLIENT_SECRET"] = "test-client-secret"
os.environ["CLIO_REDIRECT_URI"] = "http://localhost:5000/auth/callback"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_stub"
os.environ["STRIPE_PUBLIC_KEY"] = "pk_test_stub"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test_stub"
os.environ["STRIPE_PRICE_SOLO"] = "price_solo_stub"
os.environ["STRIPE_PRICE_TEAM"] = "price_team_stub"
os.environ["STRIPE_PRICE_FIRM"] = "price_firm_stub"


@pytest.fixture
def app():
    """Build a Flask app configured for tests: in-memory sqlite, dev mode.

    Each test gets a fresh DB. Env is already populated at conftest import.
    """
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
