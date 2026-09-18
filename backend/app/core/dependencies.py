"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from app.core.config import Settings, get_settings
from app.services.ai.base import LLMProvider
from app.services.moodle.client import MoodleClient
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


def get_app_settings() -> Settings:
    """Return application configuration."""
    return get_settings()


async def get_database_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a request-scoped database session.

    The session factory is created during application startup and attached
    to application state.
    """
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        yield session


def get_redis_client(request: Request) -> Redis:
    """
    Provide the shared Redis client.

    The client is created during application startup and attached to
    application state; it is not request-scoped (a single connection
    pool is reused across requests).
    """
    return request.app.state.redis_client


def get_llm_provider(request: Request) -> LLMProvider:
    """
    Provide the shared LLM provider.

    Created once during application startup and attached to application
    state, matching the redis_client pattern.
    """
    return request.app.state.llm_provider


def get_moodle_client(request: Request) -> MoodleClient:
    """
    Provide the shared Moodle client.

    May be None on application state when Moodle is not configured; API
    routes must translate that into a 5xx configuration error.
    """
    client = request.app.state.moodle_client
    if client is None:
        from app.core.exceptions import ConfigurationError

        raise ConfigurationError(
            "Moodle integration is not configured. Set MOODLE_URL and "
            "MOODLE_TOKEN in the environment."
        )
    return client