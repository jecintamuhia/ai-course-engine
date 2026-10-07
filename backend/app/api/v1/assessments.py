"""Assessment generation, retrieval, and review endpoints."""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_database_session,
    get_llm_provider,
)
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.lessons import LessonRepository
from app.schemas.assessment import (
    AssessmentGenerateRequest,
    AssessmentListResponse,
    AssessmentRead,
    AssessmentReviewRequest,
)
from app.services.ai.base import LLMProvider
from app.services.assessment.service import AssessmentService
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/assessments", tags=["assessments"])

curriculum_assessment_router = APIRouter(prefix="/curricula", tags=["assessments"])


def get_assessment_service(
    session: AsyncSession = Depends(get_database_session),
    provider: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_app_settings),
) -> AssessmentService:
    """Construct a request-scoped assessment service."""
    return AssessmentService(
        CurriculumRepository(session),
        AssessmentRepository(session),
        ChunkRepository(session),
        LessonRepository(session),
        provider,
        settings,
    )


@curriculum_assessment_router.post(
    "/{curriculum_id}/units/{unit_id}/assessments",
    response_model=AssessmentRead,
    status_code=201,
)
async def generate_unit_assessment(
    curriculum_id: uuid.UUID,
    unit_id: uuid.UUID,
    request: AssessmentGenerateRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentRead:
    """
    Generate an assessment for one weekly unit, grounded in the unit's
    textbook chunks and aligned to its learning objectives.
    """
    assessment = await service.generate_for_unit(
        curriculum_id,
        unit_id,
        assessment_type=request.assessment_type,
        max_items=request.max_items,
    )
    return AssessmentRead.model_validate(assessment)


@curriculum_assessment_router.post(
    "/{curriculum_id}/assessments/final",
    response_model=AssessmentRead,
    status_code=201,
)
async def generate_final_assessment(
    curriculum_id: uuid.UUID,
    request: AssessmentGenerateRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentRead:
    """
    Generate the course final assessment covering every weekly learning
    objective.
    """
    assessment = await service.generate_final(
        curriculum_id,
        max_items=request.max_items,
    )
    return AssessmentRead.model_validate(assessment)


@curriculum_assessment_router.get(
    "/{curriculum_id}/units/{unit_id}/assessments",
    response_model=AssessmentListResponse,
)
async def list_unit_assessments(
    curriculum_id: uuid.UUID,
    unit_id: uuid.UUID,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentListResponse:
    """List assessments generated for one weekly unit of a curriculum."""
    assessments = await service.list_by_unit(unit_id)
    scoped = [
        assessment
        for assessment in assessments
        if assessment.curriculum_id == curriculum_id
    ]
    return AssessmentListResponse(
        assessments=[AssessmentRead.model_validate(a) for a in scoped]
    )


@curriculum_assessment_router.get(
    "/{curriculum_id}/assessments", response_model=AssessmentListResponse
)
async def list_curriculum_assessments(
    curriculum_id: uuid.UUID,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentListResponse:
    """List all assessments for a curriculum."""
    assessments = await service.list_by_curriculum(curriculum_id)
    return AssessmentListResponse(
        assessments=[AssessmentRead.model_validate(a) for a in assessments]
    )


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    assessment_id: uuid.UUID,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentRead:
    """Fetch a single generated assessment."""
    assessment = await service.get_by_id(assessment_id)
    return AssessmentRead.model_validate(assessment)


@router.post("/{assessment_id}/review", response_model=AssessmentRead)
async def review_assessment(
    assessment_id: uuid.UUID,
    request: AssessmentReviewRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentRead:
    """Record a lecturer decision (approved/rejected) on an assessment."""
    assessment = await service.review(
        assessment_id,
        decision=request.decision,
        reviewer_name=request.reviewer_name,
        comments=request.comments,
    )
    return AssessmentRead.model_validate(assessment)
