"""Course content generation, review, and retrieval endpoints."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.core.dependencies import (
    get_current_user,
    get_database_session,
    get_llm_provider,
    get_redis_client,
)
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.content_generation_jobs import (
    ContentGenerationJobRepository,
)
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.lessons import LessonRepository
from app.models.lesson import Lesson
from app.models.lesson_content_block import LessonContentBlock
from app.models.user import User
from app.schemas.course_content import (
    BlockReviewRequest,
    ContentGenerationCreateResponse,
    ContentGenerationRead,
    ContentGenerationRequest,
    GenerateWeekResponse,
    LessonBlockRead,
    LessonListResponse,
    LessonRead,
    LessonReviewRequest,
    LessonSourceMapRead,
)
from app.services.ai.base import LLMProvider
from app.services.course_content.generation_jobs import ContentGenerationService
from app.services.course_content.service import CourseContentService
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/course-content", tags=["course-content"])


def get_course_content_service(
    session: AsyncSession = Depends(get_database_session),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> CourseContentService:
    """Construct a request-scoped course content service."""
    return CourseContentService(
        CurriculumRepository(session),
        ChunkRepository(session),
        LessonRepository(session),
        llm_provider,
        settings=get_settings(),
        dependency_repository=DependencyRepository(session),
    )


@router.post(
    "/weeks/{curriculum_unit_id}/generate",
    response_model=GenerateWeekResponse,
)
async def generate_week(
    curriculum_unit_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> GenerateWeekResponse:
    """
    Generate lecturer-reviewable lessons for one weekly unit of an
    approved curriculum. Approved lessons are preserved untouched; all
    other lessons are regenerated from the source material.
    """
    result = await service.generate_week(curriculum_unit_id)
    return GenerateWeekResponse(
        curriculum_unit_id=curriculum_unit_id,
        generated=[LessonRead.model_validate(lesson) for lesson in result["generated"]],
        skipped=result["skipped"],
        errors=result["errors"],
    )


@router.get(
    "/weeks/{curriculum_unit_id}/lessons",
    response_model=LessonListResponse,
)
async def list_lessons(
    curriculum_unit_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonListResponse:
    """List the generated lessons for one weekly unit, in reading order."""
    lessons = await service.list_lessons(curriculum_unit_id)
    return LessonListResponse(
        curriculum_unit_id=curriculum_unit_id,
        lessons=[LessonRead.model_validate(lesson) for lesson in lessons],
    )


@router.get("/lessons/{lesson_id}", response_model=LessonRead)
async def get_lesson(
    lesson_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonRead:
    """Return a single generated lesson with its content blocks."""
    lesson: Lesson = await service.get_lesson(lesson_id)
    return LessonRead.model_validate(lesson)


@router.get("/lessons/{lesson_id}/source-map", response_model=LessonSourceMapRead)
async def get_source_map(
    lesson_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonSourceMapRead:
    """Return the provenance of a lesson back to its source chunks."""
    return await service.get_source_map(lesson_id)


@router.post(
    "/lessons/{lesson_id}/submit-for-review",
    response_model=LessonRead,
)
async def submit_for_review(
    lesson_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonRead:
    """Move a generated lesson into the lecturer review queue."""
    lesson: Lesson = await service.submit_for_review(lesson_id)
    return LessonRead.model_validate(lesson)


@router.post("/lessons/{lesson_id}/review", response_model=LessonRead)
async def review_lesson(
    lesson_id: uuid.UUID,
    request: LessonReviewRequest,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonRead:
    """Record a lecturer's approve/reject decision on a lesson."""
    lesson: Lesson = await service.review_lesson(
        lesson_id,
        decision=request.decision,
        reviewer_name=request.reviewer_name,
        comments=request.comments,
    )
    return LessonRead.model_validate(lesson)


@router.post("/blocks/{block_id}/review", response_model=LessonBlockRead)
async def review_block(
    block_id: uuid.UUID,
    request: BlockReviewRequest,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonBlockRead:
    """Record a lecturer's approve/reject decision on a content block."""
    block: LessonContentBlock = await service.review_block(
        block_id,
        review_status=request.review_status,
        comments=request.comments,
    )
    return LessonBlockRead.model_validate(block)


@router.post("/blocks/{block_id}/regenerate", response_model=LessonBlockRead)
async def regenerate_block(
    block_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> LessonBlockRead:
    """
    Regenerate a single diagram, knowledge check, activity, external
    resource, or video block using the lesson's own source grounding.
    """
    block: LessonContentBlock = await service.regenerate_block(block_id)
    return LessonBlockRead.model_validate(block)


@router.delete("/blocks/{block_id}", status_code=204)
async def delete_block(
    block_id: uuid.UUID,
    service: CourseContentService = Depends(get_course_content_service),
) -> None:
    """Delete a single content block from a lesson."""
    await service.delete_block(block_id)


# ---------------------------------------------------------------------------
# Bulk generation across every week of a curriculum
# ---------------------------------------------------------------------------


def get_content_generation_service(
    session: AsyncSession = Depends(get_database_session),
    redis_client: Redis = Depends(get_redis_client),
) -> ContentGenerationService:
    """Construct a request-scoped bulk content-generation service."""
    return ContentGenerationService(
        CurriculumRepository(session),
        ContentGenerationJobRepository(session),
        redis_client,
    )


@router.post(
    "/curricula/{curriculum_id}/generate-all",
    response_model=ContentGenerationCreateResponse,
    status_code=202,
)
async def generate_all_lessons(
    curriculum_id: uuid.UUID,
    payload: ContentGenerationRequest,
    service: ContentGenerationService = Depends(get_content_generation_service),
    user: User = Depends(get_current_user),
) -> ContentGenerationCreateResponse:
    """
    Queue background generation of lessons for every week of a curriculum.

    Requires an approved curriculum. The run happens on the content worker
    because a full 16-week course is far more LLM work than a request can
    hold open; poll the status endpoint for progress. Idempotent — if a run
    is already in flight it is returned with ``created=false``.
    """
    job, created = await service.start(
        curriculum_id,
        rebuild_existing=payload.rebuild_existing,
        requested_by=user.id,
    )
    return ContentGenerationCreateResponse(
        job=ContentGenerationRead.model_validate(job),
        created=created,
    )


@router.get(
    "/curricula/{curriculum_id}/generate-all",
    response_model=ContentGenerationRead | None,
)
async def get_content_generation_status(
    curriculum_id: uuid.UUID,
    service: ContentGenerationService = Depends(get_content_generation_service),
) -> ContentGenerationRead | None:
    """
    Return the most recent bulk generation job for a curriculum, or null
    if one has never been requested.
    """
    job = await service.get_latest(curriculum_id)
    if job is None:
        return None
    return ContentGenerationRead.model_validate(job)
