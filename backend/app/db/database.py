"""Database engine configuration."""

from __future__ import annotations

from app.core.config import Settings
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(settings: Settings) -> AsyncEngine:
    """
    Create the asynchronous PostgreSQL engine.

    Connection pooling is configured centrally so it can be tuned per
    environment without modifying application code.
    """
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        echo=settings.debug,
    )
