"""Token-at-rest encryption, ported byte-for-byte from the Flask app's
backend/app/utils/crypto.py so both services read and write the same rows.

Same Fernet derivation: the TOKEN_ENCRYPTION_KEY env var IS the Fernet key
(no KDF), so ciphertext written by either service decrypts in the other.
Same safety behavior:

  * No key configured -> encrypt/decrypt are no-ops (plaintext passthrough).
  * decrypt_token() returns the raw value when it isn't valid Fernet
    ciphertext, so legacy plaintext rows still read correctly.

Also home to the SHA-256 helper used for MCP auth codes and tokens: we only
ever store hashes of those values, never the raw strings.
"""

import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from .config import settings

logger = logging.getLogger(__name__)

# Cache Fernet instances per key value. The env var is re-read on each call
# (cheap) so a key set after import, e.g. in a test, is picked up, while the
# Fernet object itself is built at most once per key.
_fernet_cache = {}


def _fernet():
    key = settings.token_encryption_key
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
    Fernet ciphertext (legacy plaintext) or no key is set."""
    if value is None or value == "":
        return value
    f = _fernet()
    if f is None:
        return value
    token = value.encode() if isinstance(value, str) else value
    try:
        return f.decrypt(token).decode()
    except (InvalidToken, ValueError, TypeError):
        return value


class EncryptedText(TypeDecorator):
    """Text column that transparently encrypts on write and decrypts on read."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        return decrypt_token(value)


def sha256_hex(value):
    """Hex SHA-256 of a code/token string. The database only ever sees this."""
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()
