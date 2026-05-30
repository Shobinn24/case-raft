"""Application-layer encryption for sensitive at-rest values (Clio OAuth tokens).

Uses Fernet (AES-128-CBC + HMAC) with a key from the TOKEN_ENCRYPTION_KEY env
var. Designed for a SAFE, zero-downtime rollout:

  * If TOKEN_ENCRYPTION_KEY is unset, encrypt/decrypt are no-ops (values pass
    through as plaintext). Deploying this code before the key is set therefore
    never breaks auth — it simply doesn't encrypt yet.
  * decrypt_token() returns the raw value when it isn't valid Fernet
    ciphertext, so legacy plaintext rows (written before this change) still
    read correctly. They get encrypted the next time the token is written
    (login / refresh), or immediately via scripts/encrypt_existing_tokens.py.

The EncryptedText SQLAlchemy type makes this transparent at the column level,
so existing read/write sites need no changes. Underlying DDL stays TEXT, so
switching a column to EncryptedText needs no schema migration.
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

logger = logging.getLogger(__name__)

# Cache Fernet instances per key value. We re-read the env var on each call
# (cheap) so a key set after import — e.g. in a test — is picked up, while the
# Fernet object itself (the expensive part) is built at most once per key.
_fernet_cache = {}


def _fernet():
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key:
        return None
    f = _fernet_cache.get(key)
    if f is None:
        try:
            f = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            logger.exception("TOKEN_ENCRYPTION_KEY is set but invalid; "
                             "treating tokens as plaintext")
            return None
        _fernet_cache[key] = f
    return f


def encrypt_token(value):
    """Encrypt a string for storage. No-op if no key is configured or the value
    is empty/None."""
    if value is None or value == "":
        return value
    f = _fernet()
    if f is None:
        return value
    if isinstance(value, bytes):
        value = value.decode()
    return f.encrypt(value.encode()).decode()


def decrypt_token(value):
    """Decrypt a stored string. Returns the value unchanged if it isn't valid
    Fernet ciphertext (legacy plaintext — safe transition) or no key is set."""
    if value is None or value == "":
        return value
    f = _fernet()
    if f is None:
        return value
    token = value.encode() if isinstance(value, str) else value
    try:
        return f.decrypt(token).decode()
    except (InvalidToken, ValueError, TypeError):
        # Not Fernet ciphertext — plaintext written before encryption was
        # enabled. Return as-is; it gets encrypted on the next write.
        return value


def is_encrypted(value):
    """True if `value` decrypts as valid Fernet ciphertext under the current
    key. Used by the backfill script to skip already-encrypted rows."""
    if not value:
        return False
    f = _fernet()
    if f is None:
        return False
    try:
        f.decrypt(value.encode() if isinstance(value, str) else value)
        return True
    except (InvalidToken, ValueError, TypeError):
        return False


class EncryptedText(TypeDecorator):
    """Text column that transparently encrypts on write and decrypts on read."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        return decrypt_token(value)
