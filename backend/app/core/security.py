"""Security-related application primitives."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from app.core.exceptions import AuthenticationError
from fastapi import Request
from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()


def generate_request_id() -> str:
    """Generate a cryptographically strong request correlation ID."""
    return secrets.token_hex(16)


def get_client_ip(request: Request) -> str | None:
    """
    Return the direct client address.

    Reverse-proxy trust should be explicitly configured before relying on
    forwarded headers for security-sensitive decisions.
    """
    if request.client is None:
        return None

    return request.client.host


def hash_password(password: str) -> str:
    """
    Hash a plaintext password with a per-password random salt.

    Uses the recommended Argon2 parameters from ``pwdlib``, which follows
    current OWASP guidance. The returned string is self-describing and is
    stored verbatim on the user record.
    """
    if not password:
        raise ValueError("Password must not be empty.")

    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not password:
        return False

    try:
        return _password_hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(subject: str, role: str) -> str:
    """
    Create a signed JWT access token for the given user subject.

    The token is signed with the application ``SECRET_KEY`` using HS256 and
    carries an issuance and expiry timestamp.
    """
    from app.core.config import get_settings

    settings = get_settings()

    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }

    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a signed JWT access token.

    Raises ``AuthenticationError`` when the token is malformed, expired,
    or fails signature validation.
    """
    from app.core.config import get_settings

    settings = get_settings()

    try:
        return jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired access token.") from None
