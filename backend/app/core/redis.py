"""Redis client configuration."""

from __future__ import annotations

from app.core.config import Settings
from redis.asyncio import Redis


def create_redis_client(settings: Settings) -> Redis:
    """Create the asynchronous Redis client used for job queuing."""
    return Redis.from_url(settings.redis_url, decode_responses=True)