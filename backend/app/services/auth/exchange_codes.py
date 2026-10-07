"""One-time codes that hand a freshly-minted JWT to the SPA after OAuth.

Google redirects the browser back to the API, but the SPA is what holds
the session. Passing the long-lived access token through the URL would
leak it into browser history, proxy logs, and ``Referer`` headers on the
next navigation.

Instead the callback mints a short-lived, single-use code, stores it in
Redis against the user id, and redirects the browser to the frontend with
only that code. The SPA immediately exchanges it for the token over
POST, where it stays out of URLs and logs entirely.
"""

from __future__ import annotations

import json
import secrets
import uuid

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from redis.asyncio import Redis

_PREFIX = "auth:oauth:exchange:"


def _key(code: str) -> str:
    return f"{_PREFIX}{code}"


async def issue_code(
    redis_client: Redis,
    *,
    user_id: uuid.UUID,
    settings: Settings,
) -> str:
    """Mint a single-use code bound to a user, with a short TTL."""
    code = secrets.token_urlsafe(32)
    await redis_client.set(
        _key(code),
        json.dumps({"user_id": str(user_id)}),
        ex=settings.google_oauth_exchange_ttl_seconds,
    )
    return code


async def redeem_code(
    redis_client: Redis,
    *,
    code: str,
) -> uuid.UUID:
    """
    Redeem a code for its user id, exactly once.

    Uses GETDEL semantics so a replayed or double-submitted code fails
    rather than minting a second session.
    """
    if not code or not code.strip():
        raise AuthenticationError("Missing sign-in code.")

    raw = await redis_client.getdel(_key(code.strip()))
    if raw is None:
        raise AuthenticationError("This sign-in link has expired or was already used.")

    try:
        payload = json.loads(raw)
        return uuid.UUID(payload["user_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise AuthenticationError("Invalid sign-in code.") from exc
