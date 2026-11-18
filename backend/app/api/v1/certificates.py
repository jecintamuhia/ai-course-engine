"""Public certificate verification.

The reference printed on a certificate is the only credential needed to
verify it. The response exposes exactly what the certificate states
(learner name, course title, score, dates) and nothing else, so a
holder can share the reference without exposing their account.
"""

from __future__ import annotations

from app.core.dependencies import get_database_session
from app.core.exceptions import CertificateNotFound
from app.db.repositories.certificates import CertificateRepository
from app.schemas.learner_assessment import CertificateRead
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/verify/{reference}", response_model=CertificateRead)
async def verify_certificate(
    reference: str,
    session: AsyncSession = Depends(get_database_session),
) -> CertificateRead:
    """Verify a certificate by its public reference."""
    repository = CertificateRepository(session)
    certificate = await repository.get_by_reference(reference.strip())
    if not certificate:
        raise CertificateNotFound("No certificate matches that reference.")
    return CertificateRead.model_validate(certificate)
