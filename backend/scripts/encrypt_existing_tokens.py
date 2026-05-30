"""Backfill: encrypt any plaintext Clio tokens in the users table at rest.

Idempotent — rows already encrypted under the current TOKEN_ENCRYPTION_KEY are
left alone. Safe to run more than once.

Run AFTER deploying the EncryptedText change and setting TOKEN_ENCRYPTION_KEY:

    cd backend
    TOKEN_ENCRYPTION_KEY=... DATABASE_URL=... python -m scripts.encrypt_existing_tokens

Note: the app already encrypts tokens on every write (login / refresh), so rows
migrate naturally over time even without this script. This just encrypts the
existing stragglers immediately.
"""

import os
import sys

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.utils.crypto import encrypt_token, is_encrypted


def main():
    if not os.environ.get("TOKEN_ENCRYPTION_KEY"):
        print("TOKEN_ENCRYPTION_KEY not set — refusing to run (tokens would stay plaintext).")
        return 1

    app = create_app()
    with app.app_context():
        rows = db.session.execute(
            text("SELECT id, clio_access_token, clio_refresh_token FROM users")
        ).fetchall()

        updated = 0
        for rid, access, refresh in rows:
            new_access = access if is_encrypted(access) else encrypt_token(access)
            new_refresh = refresh if is_encrypted(refresh) else encrypt_token(refresh)
            if new_access != access or new_refresh != refresh:
                # Raw UPDATE bypasses the EncryptedText type so we store the
                # already-encrypted value verbatim (no double-encryption).
                db.session.execute(
                    text("UPDATE users SET clio_access_token = :a, "
                         "clio_refresh_token = :r WHERE id = :i"),
                    {"a": new_access, "r": new_refresh, "i": rid},
                )
                updated += 1

        db.session.commit()
        print(f"Encrypted tokens for {updated} of {len(rows)} users.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
