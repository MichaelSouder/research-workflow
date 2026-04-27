"""Bcrypt password hashing for optional password login (platform-provisioned users)."""

import bcrypt

MIN_PASSWORD_LEN = 8

# google_id prefix for users created by superuser before first Google OAuth link
PENDING_GOOGLE_PREFIX = "pending:"


def hash_password(plain: str) -> str:
    h = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return h.decode("ascii")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False
