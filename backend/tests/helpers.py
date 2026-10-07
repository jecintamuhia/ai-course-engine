"""Shared helpers for route-level tests with the auth dependency injected."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.dependencies import get_current_user
from app.models.user import User, UserRole

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def make_test_user(
    *,
    role: UserRole = UserRole.ADMIN,
    email: str = "admin@test.local",
    user_id: uuid.UUID | None = None,
) -> User:
    """Build an authenticated test user that never touches the database."""
    now = datetime.now(UTC)
    return User(
        id=user_id or TEST_USER_ID,
        email=email,
        password_hash="_",
        full_name="Test User",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def install_auth_override(app, *, role: UserRole = UserRole.ADMIN) -> None:
    """Make every protected route appear authenticated as ``role``."""
    app.dependency_overrides[get_current_user] = lambda: make_test_user(role=role)
