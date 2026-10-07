"""Repository for User persistence operations."""

from __future__ import annotations

import uuid

from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class UserRepository:
    """Data-access layer for User records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key."""
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by its normalized email address."""
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        """Stage a new user for persistence."""
        self._session.add(user)
        await self._session.flush()
        return user

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()
