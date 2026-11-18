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


class FakeRedis:
    """Small in-memory Redis stand-in for auth route tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key, value, ex=None):
        self.store[str(key)] = str(value)
        if isinstance(ex, int) and ex > 0:
            self.expirations[str(key)] = ex
        return True

    async def get(self, key):
        value = self.store.get(str(key))
        return value

    async def getdel(self, key):
        return self.store.pop(str(key), None)

    async def incr(self, key):
        key = str(key)
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key, seconds):
        self.expirations[str(key)] = int(seconds)
        return True

    async def ttl(self, key):
        return self.expirations.get(str(key), -1)

    async def ping(self):
        return True

    async def aclose(self):
        return None
