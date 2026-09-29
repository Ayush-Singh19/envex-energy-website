"""Password hashing (bcrypt) and session tokens (JWT in an httpOnly cookie)."""

from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings

BCRYPT_ROUNDS = 12
JWT_ALGORITHM = "HS256"
TOKEN_TYPE = "admin_session"  # noqa: S105  (a claim value, not a secret)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # malformed hash or >72-byte password
        return False


@lru_cache
def dummy_hash() -> str:
    """Checked against when the email is unknown, so response time doesn't reveal it."""
    return hash_password("timing-equaliser-not-a-real-password")


def create_access_token(subject: str, settings: Settings, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {
        "sub": subject,
        "typ": TOKEN_TYPE,
        "iat": int(issued.timestamp()),
        "exp": issued + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any] | None:
    try:
        claims = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return claims if claims.get("typ") == TOKEN_TYPE else None
