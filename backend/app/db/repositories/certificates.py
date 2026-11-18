"""Repository for issued certificates."""

from __future__ import annotations

import uuid

from app.models.certificate import Certificate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class CertificateRepository:
    """Data-access layer for certificates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, certificate: Certificate) -> Certificate:
        """Stage a certificate for persistence."""
        self._session.add(certificate)
        await self._session.flush()
        return certificate

    async def get_by_reference(self, reference: str) -> Certificate | None:
        """Look up a certificate by its public reference."""
        stmt = select(Certificate).where(Certificate.reference == reference)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_for_learner_course(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> Certificate | None:
        """Return the certificate for one learner on one course."""
        stmt = select(Certificate).where(
            Certificate.user_id == user_id,
            Certificate.course_id == course_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Certificate]:
        """Return every certificate a learner has earned, newest first."""
        stmt = (
            select(Certificate)
            .where(Certificate.user_id == user_id)
            .order_by(Certificate.issued_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()
