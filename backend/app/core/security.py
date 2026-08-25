from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    """

    if length < 16:
        raise ValueError("Token length must be at least 16 characters.")

    return secrets.token_urlsafe(length)


def hash_token(token: str) -> str:
    """
    Produce a SHA-256 digest suitable for storing a token fingerprint.

    Raw credentials should never be stored in the database.
    """

    if not token:
        raise ValueError("Token cannot be empty.")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def verify_token(
    token: str,
    expected_hash: str,
) -> bool:
    """
    Verify a token using constant-time comparison.
    """

    if not token or not expected_hash:
        return False

    actual_hash = hash_token(token)

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )