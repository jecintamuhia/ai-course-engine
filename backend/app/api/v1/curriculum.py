"""Curriculum generation, review, and retrieval endpoints."""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_database_session,
)
from app.db.repositories.assessments import AssessmentRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.dependencies import DependencyRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.lessons import LessonRepository
from app.db.repositories.quality_reports import QualityReportRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.models.curriculum_review import ReviewDecision
from app.schemas.curriculum import (
    CurriculumDetailRead,
    CurriculumGenerateRequest,
    CurriculumGenerateResponse,
    CurriculumListResponse,
    CurriculumRead,
    CurriculumReviewRequest,
)
from app.schemas.qa import (
    CoverageReportRead,
    QAReportRead,
    QAReportResponse,
)
from app.services.curriculum.service import CurriculumService
from app.services.planner.four_month_planner import FourMonthPlanner
from app.services.qa.service import QADependencies, QAService
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/curricula", tags=["curricula"])


def get_curriculum_service(
    session: AsyncSession = Depends(get_database_session),
) -> CurriculumService:
    """Construct a request-scoped curriculum service."""
    return CurriculumService(
        DocumentRepository(session),
        TopicRepository(session),
        DependencyRepository(session),
        CurriculumRepository(session),
        planner=FourMonthPlanner(),
    )


def get_qa_service(
    session: AsyncSession = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings),
) -> QAService:
    """Construct a request-scoped content-QA service."""
    return QAService(
        QADependencies(
            curriculum=CurriculumRepository(session),
            dependencies=DependencyRepository(session),
            topics=TopicRepository(session),
            lessons=LessonRepository(session),
            structure=StructureRepository(session),
            documents=DocumentRepository(session),
            quality_reports=QualityReportRepository(session),
            assessments=AssessmentRepository(session),
            courses=CourseRepository(session),
        ),
        settings,
    )


@router.post("", response_model=CurriculumGenerateResponse, status_code=201)
async def generate_curriculum(
    request: CurriculumGenerateRequest,
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumGenerateResponse:
    """
    Generate a deterministic weekly curriculum for a document.

    Requires topic analysis (POST /documents/{id}/analyze) and the
    dependency graph to already exist for the document. Each call
    creates a new curriculum version; previous latest versions are
    marked superseded.
    """
    curriculum = await service.generate_curriculum(
        request.document_id,
        total_weeks=request.total_weeks,
        learning_days_per_week=request.learning_days_per_week,
        hours_per_day=request.hours_per_day,
        start_date=request.start_date,
        title=request.title,
        description=request.description,
    )
    created = await service.get_by_id(curriculum.id)
    return CurriculumGenerateResponse(curriculum=CurriculumRead.model_validate(created))


@router.get("", response_model=CurriculumListResponse)
async def list_curricula(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> CurriculumListResponse:
    """List all latest-version curricula generated for a document."""
    repository = CurriculumRepository(session)
    curricula = await repository.list_latest_by_document(document_id)
    return CurriculumListResponse(
        curricula=[CurriculumRead.model_validate(c) for c in curricula]
    )


@router.get("/{curriculum_id}/export")
async def export_curriculum(
    curriculum_id: uuid.UUID,
    service: CurriculumService = Depends(get_curriculum_service),
) -> JSONResponse:
    """
    Download the Moodle-ready curriculum export (fallback delivery path).

    Returns a structured JSON document describing the planned course —
    title, description, full week schedule, per-topic learning objectives,
    prerequisites, difficulty/workload, and source provenance. The export
    is a reference document, NOT a Moodle backup, and never claims to be
    importable into Moodle.
    """
    payload = await service.export_payload(curriculum_id)
    filename = f"curriculum-{curriculum_id}.moodle-export.json"
    return JSONResponse(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{curriculum_id}", response_model=CurriculumDetailRead)
async def get_curriculum(
    curriculum_id: uuid.UUID,
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumDetailRead:
    """Fetch a curriculum by ID, including its weekly units and reviews."""
    curriculum = await service.get_by_id(curriculum_id)
    return CurriculumDetailRead.model_validate(curriculum)


@router.post("/{curriculum_id}/submit-for-review", response_model=CurriculumRead)
async def submit_curriculum_for_review(
    curriculum_id: uuid.UUID,
    service: CurriculumService = Depends(get_curriculum_service),
) -> CurriculumRead:
    """Move a DRAFT curriculum into the lecturer review queue."""
    curriculum = await service.submit_for_review(curriculum_id)
    refreshed = await service.get_by_id(curriculum.id)
    return CurriculumRead.model_validate(refreshed)


@router.post("/{curriculum_id}/review", response_model=CurriculumRead)
async def review_curriculum(
    curriculum_id: uuid.UUID,
    request: CurriculumReviewRequest,
    service: CurriculumService = Depends(get_curriculum_service),
    qa_service: QAService = Depends(get_qa_service),
) -> CurriculumRead:
    """
    Record a lecturer decision (approved/rejected) on a curriculum.

    Only curricula in AWAITING_REVIEW status can be reviewed. Approval
    is gated by content-QA: a curriculum whose latest automated QA
    verdict is ``fail`` is rejected with 409 `qa_blocked` and the
    severe findings the lecturer must resolve. Approved curricula
    become publishable to Moodle.
    """
    if request.decision == ReviewDecision.APPROVED.value:
        await qa_service.assert_qa_pass(curriculum_id)

    curriculum = await service.review(
        curriculum_id,
        decision=ReviewDecision(request.decision),
        reviewer_name=request.reviewer_name,
        comments=request.comments,
    )
    refreshed = await service.get_by_id(curriculum.id)
    return CurriculumRead.model_validate(refreshed)


@router.post("/{curriculum_id}/qa", response_model=QAReportResponse)
async def run_content_qa(
    curriculum_id: uuid.UUID,
    service: QAService = Depends(get_qa_service),
) -> QAReportResponse:
    """
    Run automated content-QA over a curriculum and persist the report.

    Checks coverage, duplication, provenance, content depth, learning
    design, and Moodle readiness. ``blocked=true`` in the response means
    the curriculum currently fails QA and cannot yet be approved or
    published.
    """
    return await service.run_curriculum_qa(curriculum_id)


@router.get("/{curriculum_id}/quality-report", response_model=QAReportRead)
async def get_quality_report(
    curriculum_id: uuid.UUID,
    service: QAService = Depends(get_qa_service),
) -> QAReportRead:
    """
    Return the latest persisted content-QA report for a curriculum.
    """
    report = await service.get_latest_report(curriculum_id)
    return QAReportRead.model_validate(report)


@router.get("/{curriculum_id}/coverage", response_model=CoverageReportRead)
async def get_coverage_report(
    curriculum_id: uuid.UUID,
    service: QAService = Depends(get_qa_service),
) -> CoverageReportRead:
    """
    Return the textbook coverage report for a curriculum's document:
    how completely the source textbook is mapped, lesson coverage,
    blocked duplicates, and teaching-block counts.
    """
    return await service.build_coverage_report(curriculum_id)
