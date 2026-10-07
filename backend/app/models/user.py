"""User model: authenticated application users (admins and lecturers)."""

from __future__ import annotations

import enum

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Boolean, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class UserRole(str, enum.Enum):
    """Roles that can interact with the application."""

    ADMIN = "admin"
    LECTURER = "lecturer"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An authenticated application user (administrator or lecturer).

    Passwords are stored exclusively as Argon2 hashes; plaintext passwords
    are never persisted.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=UserRole.LECTURER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<User id={self.id} email={self.email!r} "
            f"role={self.role.value} active={self.is_active}>"
        )
