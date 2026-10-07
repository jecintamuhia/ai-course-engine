"""Moodle integration status, publish, and verification endpoints."""

from __future__ import annotations

import uuid

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_database_session,
    get_moodle_client,
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
from app.schemas.moodle import (
    MoodleConnectionCheck,
    MoodleConnectionStatus,
    MoodlePreflightCheck,
    MoodlePreflightIssue,
    MoodlePreflightResponse,
    MoodlePublishRequest,
    MoodlePublishResponse,
    MoodleVerifyResponse,
)
from app.services.moodle.client import MoodleClient
from app.services.moodle.lessons import build_lesson_renderer
from app.services.moodle.preflight import (
    check_to_dict,
    issue_to_dict,
    run_readiness_check,
)
from app.services.moodle.status import connection_status
from app.services.moodle.sync import MoodleSyncService
from app.services.qa.service import QADependencies, QAService
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/moodle", tags=["moodle"])


def get_moodle_sync_service(
    session: AsyncSession = Depends(get_database_session),
    client: MoodleClient = Depends(get_moodle_client),
    settings: Settings = Depends(get_app_settings),
) -> MoodleSyncService:
    """Construct a request-scoped Moodle sync service."""
    return MoodleSyncService(
        client,
        CurriculumRepository(session),
        CourseRepository(session),
        moodle_base_url=settings.moodle_url,
        moodle_course_category_id=settings.moodle_course_category_id,
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


@router.get("/status", response_model=MoodleConnectionStatus)
async def moodle_status(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> MoodleConnectionStatus:
    """
    Report the configured Moodle connection state.

    Returns ``configured=false`` when MOODLE_URL/MOODLE_TOKEN are not
    set, and a permissive ``connected=false`` with an error message when
    the configured endpoint cannot be reached.
    """
    client: MoodleClient | None = request.app.state.moodle_client
    return MoodleConnectionStatus(**await connection_status(settings, client))


@router.get("/check", response_model=MoodleConnectionCheck)
async def moodle_check(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> MoodleConnectionCheck:
    """
    Run a deeper, read-only Moodle health probe.

    When connected, verifies that the default course category actually
    exists (``MOODLE_COURSE_CATEGORY_ID``), counts how many categories
    the token can see, and includes the site info from the status check.
    Never writes to Moodle.
    """
    client: MoodleClient | None = request.app.state.moodle_client
    status = await connection_status(settings, client)

    check = MoodleConnectionCheck(
        **status,
        default_category_id=(
            settings.moodle_course_category_id
            if settings.moodle_course_category_id
            else None
        ),
    )

    if not status["connected"] or client is None:
        return check

    try:
        category_matches = await client.get_categories(
            category_id=settings.moodle_course_category_id
        )
        all_categories = await client.get_categories()
    except Exception as exc:  # noqa: BLE001 - permissive health surface
        check.error = str(exc)
        check.connected = False
        return check

    check.default_category_found = bool(category_matches)
    check.categories_visible = len(all_categories)
    return check


@router.get("/preflight", response_model=MoodlePreflightResponse)
async def moodle_preflight(
    request: Request,
    settings: Settings = Depends(get_app_settings),
) -> MoodlePreflightResponse:
    """
    Structured Moodle readiness report for publishing.

    Runs only read-only Moodle calls and returns a checklist (``checks``)
    plus a stable list of blocking issues (``blocking_issues`` /
    ``issues``): auth/token failures, missing capabilities, unsupported
    web service functions, an invalid target category, invalid
    parameters, and transient failures. Each issue names the web service
    function and capability required plus the action a Moodle
    administrator must take. Nothing is written to Moodle and no
    curriculum is modified.
    """
    client: MoodleClient | None = request.app.state.moodle_client
    result = await run_readiness_check(
        client,
        category_id=settings.moodle_course_category_id,
    )
    issues = [MoodlePreflightIssue(**issue_to_dict(issue)) for issue in result.issues]
    return MoodlePreflightResponse(
        ready=result.ready,
        configured=result.configured,
        moodle_url=result.moodle_url,
        site_name=result.site_name,
        site_url=result.site_url,
        api_version=result.api_version,
        username=result.username,
        functions_available=result.functions_available,
        functions_required=result.functions_required,
        capabilities_required=result.capabilities_required,
        category_id=result.category_id,
        category_found=result.category_found,
        checks=[
            MoodlePreflightCheck(**check_to_dict(check)) for check in result.checks
        ],
        issues=issues,
        blocking_issues=issues,
        checked_at=result.checked_at,
    )


@router.post("/publish/{curriculum_id}", response_model=MoodlePublishResponse)
async def publish_curriculum(
    curriculum_id: uuid.UUID,
    request: MoodlePublishRequest | None = None,
    service: MoodleSyncService = Depends(get_moodle_sync_service),
    qa_service: QAService = Depends(get_qa_service),
    session: AsyncSession = Depends(get_database_session),
) -> MoodlePublishResponse:
    """
    Publish an APPROVED curriculum to Moodle (idempotent).

    Re-publishing the same curriculum updates the existing Moodle course
    (found by idnumber ``ai-ece-<curriculum_id>``) and only adds missing
    page resources; it never duplicates. Lecturer-APPROVED lessons are
    published as additional page resources inside their weekly sections.

    Publishing is gated by content-QA: a curriculum whose latest QA
    verdict is ``fail`` is rejected with 409 `qa_blocked` before any
    Moodle write, matching the review gate.
    """
    await qa_service.assert_qa_pass(curriculum_id)

    body = request or MoodlePublishRequest()

    lesson_repository = LessonRepository(session)
    publishable_lessons = await lesson_repository.list_publishable_by_curriculum(
        curriculum_id
    )
    await lesson_repository.commit()

    result = await service.publish_curriculum(
        curriculum_id,
        idnumber_override=body.idnumber,
        fullname_override=body.fullname,
        shortname_override=body.shortname,
        category_id_override=body.category_id,
        lesson_renderer=build_lesson_renderer(publishable_lessons),
    )
    return MoodlePublishResponse(
        course_id=str(result.course_id),
        moodle_course_id=result.moodle_course_id,
        course_fullname=result.course_fullname,
        course_shortname=result.course_shortname,
        course_url=result.course_url,
        idnumber=result.idnumber,
        created=result.created,
        sections_published=result.sections_published,
        resources_published=result.resources_published,
        verified=result.verified,
    )


@router.post("/verify/{course_id}", response_model=MoodleVerifyResponse)
async def verify_course(
    course_id: uuid.UUID,
    service: MoodleSyncService = Depends(get_moodle_sync_service),
) -> MoodleVerifyResponse:
    """
    Verify a published course's presence and contents in Moodle.

    Reports the section/module counts returned by the course contents
    web service for the stored Moodle course id.
    """
    result = await service.verify_course(course_id)
    return MoodleVerifyResponse(**result)
