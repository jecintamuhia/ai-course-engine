from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from app.core.config import get_settings


def create_database_engine() -> AsyncEngine:
    """
    Create the application's asynchronous SQLAlchemy engine.
    """

    settings = get_settings()

    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
    )


engine = create_database_engine()