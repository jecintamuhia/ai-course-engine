"""Security-related application primitives."""

from __future__ import annotations

import secrets

from fastapi import Request


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