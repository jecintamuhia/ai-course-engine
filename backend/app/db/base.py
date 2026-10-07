"""SQLAlchemy declarative base."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    """Reusable UUID primary-key definition."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def utcnow() -> datetime:
    """Timezone-aware current time for client-side column defaults."""
    return datetime.now(UTC)


class TimestampMixin:
    """Reusable timezone-aware creation/update timestamps.

    Values are computed client-side (with a ``server_default`` fallback
    for rows created outside the ORM) so SQLAlchemy never has to refresh
    them from the database after flush; otherwise a post-commit read of
    ``created_at``/``updated_at`` triggers a lazy load that raises
    ``MissingGreenlet`` in async contexts.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )


def model_to_dict(model: Base) -> dict[str, Any]:
    """
    Convert a SQLAlchemy model's mapped columns into a dictionary.

    This utility is intentionally limited to mapped columns and does not
    traverse relationships.
    """
    return {
        column.name: getattr(model, column.name) for column in model.__table__.columns
    }
