"""Redis-backed throttling for password sign-in attempts.

The limiter uses two independent fixed-window buckets:

* a hashed email bucket, which protects one account from password guessing;
* a hashed client-IP bucket, which caps attempts from one source.

Both buckets are incremented before the credential check. A successful
login is still counted: the goal is to bound work and guessing, not to
reward a lucky guess with a clean slate. If Redis is unavailable the
endpoint fails closed with a 503 rather than silently removing the
protection.
"""

from __future__ import annotations

import hashlib

from app.core.config import Settings
from app.core.exceptions import RateLimitedError, RateLimitUnavailableError
from app.core.logging import get_logger
from fastapi import Request
from redis.asyncio import Redis

logger = get_logger(__name__)

_PREFIX = "auth:login:"


def _digest(value: str) -> str:
    """Hash a bucket value so raw emails and IPs never enter Redis keys."""
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def _email_key(email: str) -> str:
    return f"{_PREFIX}email:{_digest(email)}"


def _ip_key(client_ip: str) -> str:
    return f"{_PREFIX}ip:{_digest(client_ip)}"


def client_ip(request: Request, *, trust_proxy_headers: bool = False) -> str:
    """
    Return the client address used for the IP bucket.

    ``X-Forwarded-For`` is attacker-controlled input. It is only honoured
    when the deployment explicitly declares that the service sits behind a
    trusted reverse proxy (Render/Caddy), and then only the right-most
    value is used because that value is the one appended by the nearest
    proxy. Without that declaration the direct socket peer is used, so a
    caller cannot pick its own bucket by spoofing the header.
    """
    if trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            candidate = forwarded.split(",")[-1].strip()
            if candidate:
                return candidate

    if request.client is not None and request.client.host:
        return request.client.host

    return "unknown"


async def _consume_bucket(
    redis_client: Redis,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment one fixed-window bucket and raise when it is exhausted."""
    count = await redis_client.incr(key)

    if count == 1:
        await redis_client.expire(key, window_seconds)

    if count <= limit:
        return

    ttl = await redis_client.ttl(key)
    retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds

    raise RateLimitedError(
        "Too many sign-in attempts. Please try again later.",
        retry_after_seconds=retry_after,
    )


async def enforce_login_rate_limit(
    redis_client: Redis,
    *,
    settings: Settings,
    email: str,
    client_ip_address: str,
) -> None:
    """
    Enforce the email and IP login buckets.

    The caller must invoke this before checking the supplied password. Any
    Redis failure other than an exhausted bucket is translated into a 503
    so a degraded limiter cannot silently become no limiter.
    """
    if not settings.login_rate_limit_enabled:
        return

    window = settings.login_rate_limit_window_seconds

    try:
        await _consume_bucket(
            redis_client,
            key=_email_key(email),
            limit=settings.login_rate_limit_email_attempts,
            window_seconds=window,
        )
        await _consume_bucket(
            redis_client,
            key=_ip_key(client_ip_address),
            limit=settings.login_rate_limit_ip_attempts,
            window_seconds=window,
        )
    except RateLimitedError:
        raise
    except Exception as exc:  # noqa: BLE001 - convert to a safe 503
        logger.error(
            "Login rate limiter unavailable exception=%s",
            type(exc).__name__,
        )
        raise RateLimitUnavailableError(
            "Sign-in is temporarily unavailable. Please try again later."
        ) from exc
