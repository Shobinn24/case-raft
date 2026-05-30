"""Tests for Clio token encryption at rest (app/utils/crypto.py)."""

import os

from cryptography.fernet import Fernet
from sqlalchemy import text


def test_token_encrypted_at_rest_and_roundtrips(app):
    from app.extensions import db
    from app.models.user import User

    os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    try:
        u = User(
            email="enc@example.com",
            clio_access_token="secret-access",
            clio_refresh_token="secret-refresh",
        )
        db.session.add(u)
        db.session.commit()
        uid = u.id

        # Raw stored value is Fernet ciphertext, not the plaintext.
        raw = db.session.execute(
            text("SELECT clio_access_token FROM users WHERE id = :i"), {"i": uid}
        ).scalar()
        assert raw != "secret-access"
        assert raw.startswith("gAAAA")  # Fernet token prefix

        # ORM read transparently decrypts back to the original plaintext.
        db.session.expire_all()
        got = db.session.get(User, uid)
        assert got.clio_access_token == "secret-access"
        assert got.clio_refresh_token == "secret-refresh"
    finally:
        os.environ.pop("TOKEN_ENCRYPTION_KEY", None)


def test_legacy_plaintext_still_reads(app):
    """A row written before encryption was enabled must still read correctly
    (decrypt falls back to returning the raw plaintext)."""
    from app.extensions import db
    from app.models.user import User

    os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
    db.session.execute(
        text("INSERT INTO users (email, clio_access_token, clio_refresh_token) "
             "VALUES (:e, :a, :r)"),
        {"e": "legacy@example.com", "a": "legacy-plain", "r": "legacy-refresh"},
    )
    db.session.commit()

    os.environ["TOKEN_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    try:
        db.session.expire_all()
        u = User.query.filter_by(email="legacy@example.com").first()
        assert u.clio_access_token == "legacy-plain"
        assert u.clio_refresh_token == "legacy-refresh"
    finally:
        os.environ.pop("TOKEN_ENCRYPTION_KEY", None)


def test_no_key_is_passthrough():
    """With no key configured, encrypt/decrypt are no-ops."""
    from app.utils import crypto

    os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
    assert crypto.encrypt_token("hello") == "hello"
    assert crypto.decrypt_token("hello") == "hello"
    assert crypto.is_encrypted("hello") is False
