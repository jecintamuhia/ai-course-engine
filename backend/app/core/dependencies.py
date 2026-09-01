"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings


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