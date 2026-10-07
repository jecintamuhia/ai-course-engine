"""Route-level tests for the Phase 1 QA, coverage, and assessment endpoints.

Exercises the new endpoints by overriding service dependencies with
mocks (no database). Verifies wiring, response shapes, and the QA gates
behind curriculum approval and Moodle publishing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import app.services.assessment.service as assessment_service_module
import httpx
from app.api.v1.assessments import get_assessment_service
from app.api.v1.curriculum import get_curriculum_service, get_qa_service
from app.api.v1.moodle import get_moodle_sync_service
from app.api.v1.moodle import get_qa_service as get_moodle_qa_service
from app.core.dependencies import get_database_session
from app.core.exceptions import ContentQAError, QualityReportNotFound
from app.main import app
from app.models.assessment import Assessment, AssessmentStatus, AssessmentType
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_review import ReviewDecision
from app.schemas.qa import (
    QAAreaStatus,
    QAFinding,
    QAReportRead,
    QAReportResponse,
)
from app.services.curriculum.service import CurriculumService
from app.services.moodle.sync import MoodleSyncService
from app.services.qa.service import QAService
from tests.helpers import install_auth_override

CURRICULUM_QA_URL = "/api/v1/curricula/{id}/qa"
QUALITY_REPORT_URL = "/api/v1/curricula/{id}/quality-report"
COVERAGE_URL = "/api/v1/curricula/{id}/coverage"
REVIEW_URL = "/api/v1/curricula/{id}/review"
PUBLISH_URL = "/api/v1/moodle/publish/{id}"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _curriculum() -> Curriculum:
    curriculum = Curriculum(
        id=_uuid(),
        document_id=_uuid(),
        title="Design of Experiments",
        description=None,
        status=CurriculumStatus.AWAITING_REVIEW,
        total_weeks=16,
        learning_days_per_week=5,
        hours_per_day=4,
        max_weekly_workload_minutes=600,
        min_topic_allocation_minutes=60,
        max_topic_allocation_minutes=240,
        version_number=1,
        is_latest_version=True,
    )
    curriculum.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    curriculum.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return curriculum


def _assessment() -> Assessment:
    assessment = Assessment(
        id=_uuid(),
        curriculum_id=_uuid(),
        curriculum_unit_id=_uuid(),
        week_number=1,
        title="Week 1 Quiz",
        description="Check understanding.",
        assessment_type=AssessmentType.WEEKLY_QUIZ,
        learning_objectives=["LO1"],
        estimated_minutes=30,
        items=[
            {
                "kind": "multiple_choice",
                "prompt": "q",
                "learning_objective": "LO1",
                "options": [{"id": "a", "text": "A"}],
                "explanation": "e",
            }
        ],
        alignment=[
            {
                "learning_objective": "LO1",
                "lesson_id": None,
                "lesson_title": None,
                "unit_week": None,
                "evidence": [],
            }
        ],
        generation_errors=[],
        status=AssessmentStatus.AWAITING_REVIEW,
    )
    assessment.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    assessment.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return assessment


def _qa_report(curriculum_id: uuid.UUID) -> QAReportResponse:
    report = QAReportRead(
        id=_uuid(),
        curriculum_id=curriculum_id,
        version_number=1,
        verdict="pass",
        areas={"coverage": QAAreaStatus(status="pass", findings=0)},
        findings=[
            QAFinding(rule="coverage", code="mock", severity="info", message="ok")
        ],
        summary={"coverage": 0},
        checked_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return QAReportResponse(report=report, blocked=False)


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
    )


async def _clear_overrides() -> None:
    app.dependency_overrides.clear()
    install_auth_override(app)


def _override_qa(*, raise_on_assert: bool = False):
    qa_service = AsyncMock(spec=QAService)
    qa_service.run_curriculum_qa = AsyncMock(
        side_effect=lambda curriculum_id: _qa_report(curriculum_id)
    )
    if raise_on_assert:
        qa_service.assert_qa_pass = AsyncMock(
            side_effect=ContentQAError("blocked", details={"verdict": "fail"})
        )
    else:
        qa_service.assert_qa_pass = AsyncMock(return_value=None)
    return qa_service


async def test_qa_run_endpoint_returns_report():
    await _clear_overrides()
    qa_service = _override_qa()
    app.dependency_overrides[get_qa_service] = lambda: qa_service
    curriculum_id = _uuid()

    try:
        async with await _client() as client:
            response = await client.post(CURRICULUM_QA_URL.format(id=curriculum_id))
        assert response.status_code == 200
        body = response.json()
        assert body["blocked"] is False
        assert body["report"]["verdict"] == "pass"
        assert body["report"]["curriculum_id"] == str(curriculum_id)
    finally:
        await _clear_overrides()


async def test_quality_report_endpoint_404_when_missing():
    await _clear_overrides()
    qa_service = AsyncMock(spec=QAService)
    qa_service.get_latest_report = AsyncMock(side_effect=QualityReportNotFound("none"))
    app.dependency_overrides[get_qa_service] = lambda: qa_service

    try:
        async with await _client() as client:
            response = await client.get(QUALITY_REPORT_URL.format(id=_uuid()))
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "quality_report_not_found"
    finally:
        await _clear_overrides()


async def test_coverage_endpoint_returns_report():
    await _clear_overrides()
    qa_service = AsyncMock(spec=QAService)
    qa_service.build_coverage_report = AsyncMock(
        return_value={
            "document_id": str(_uuid()),
            "document_title": "textbook.pdf",
            "curriculum_id": str(_uuid()),
            "chapters": 1,
            "sections": 4,
            "topic_count": 3,
            "mapped_topic_count": 3,
            "lesson_count": 3,
            "coverage_percent": 100.0,
            "duplicate_topics_removed": 0,
            "unresolved_topic_count": 0,
            "unresolved_topics": [],
            "resource_count": 0,
            "video_count": 0,
            "activity_count": 0,
            "knowledge_check_count": 0,
            "diagram_count": 0,
            "topics": [],
        }
    )
    app.dependency_overrides[get_qa_service] = lambda: qa_service

    try:
        async with await _client() as client:
            response = await client.get(COVERAGE_URL.format(id=_uuid()))
        assert response.status_code == 200
        assert response.json()["coverage_percent"] == 100.0
    finally:
        await _clear_overrides()


async def test_review_approval_blocked_when_qa_fails():
    await _clear_overrides()
    qa_service = _override_qa(raise_on_assert=True)
    app.dependency_overrides[get_qa_service] = lambda: qa_service
    app.dependency_overrides[get_database_session] = lambda: AsyncMock()

    try:
        async with await _client() as client:
            response = await client.post(
                REVIEW_URL.format(id=_uuid()),
                json={"decision": "approved"},
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "qa_blocked"
    finally:
        await _clear_overrides()


async def test_review_approval_proceeds_when_qa_passes():
    await _clear_overrides()
    curriculum = _curriculum()
    qa_service = _override_qa()
    curriculum_service = AsyncMock(spec=CurriculumService)
    curriculum_service.review = AsyncMock(return_value=curriculum)
    curriculum_service.get_by_id = AsyncMock(return_value=curriculum)
    app.dependency_overrides[get_qa_service] = lambda: qa_service
    app.dependency_overrides[get_curriculum_service] = lambda: curriculum_service

    try:
        async with await _client() as client:
            response = await client.post(
                REVIEW_URL.format(id=curriculum.id),
                json={
                    "decision": ReviewDecision.APPROVED.value,
                    "reviewer_name": "Dr. Smith",
                },
            )
        assert response.status_code == 200
        assert response.json()["id"] == str(curriculum.id)
        assert response.json()["title"] == "Design of Experiments"
        curriculum_service.review.assert_awaited_with(
            curriculum.id,
            decision=ReviewDecision.APPROVED,
            reviewer_name="Dr. Smith",
            comments=None,
        )
    finally:
        await _clear_overrides()


async def test_moodle_publish_blocked_when_qa_fails():
    await _clear_overrides()
    qa_service = _override_qa(raise_on_assert=True)
    sync_service = AsyncMock(spec=MoodleSyncService)
    app.dependency_overrides[get_moodle_qa_service] = lambda: qa_service
    app.dependency_overrides[get_moodle_sync_service] = lambda: sync_service
    app.dependency_overrides[get_database_session] = lambda: AsyncMock()

    try:
        async with await _client() as client:
            response = await client.post(PUBLISH_URL.format(id=_uuid()))
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "qa_blocked"
        sync_service.publish_curriculum.assert_not_awaited()
    finally:
        await _clear_overrides()


async def test_unit_assessment_generation_endpoint():
    await _clear_overrides()
    assessment = _assessment()
    assessment_service = AsyncMock(spec=assessment_service_module.AssessmentService)
    assessment_service.generate_for_unit = AsyncMock(return_value=assessment)
    app.dependency_overrides[get_assessment_service] = lambda: assessment_service

    try:
        async with await _client() as client:
            response = await client.post(
                f"/api/v1/curricula/{assessment.curriculum_id}/units/"
                f"{assessment.curriculum_unit_id}/assessments",
                json={"max_items": 5},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == str(assessment.id)
        assert body["assessment_type"] == "weekly_quiz"
        assert body["items"][0]["kind"] == "multiple_choice"
    finally:
        await _clear_overrides()


async def test_assessment_review_endpoint():
    await _clear_overrides()
    assessment = _assessment()
    assessment.status = AssessmentStatus.APPROVED
    assessment_service = AsyncMock(spec=assessment_service_module.AssessmentService)
    assessment_service.review = AsyncMock(return_value=assessment)
    app.dependency_overrides[get_assessment_service] = lambda: assessment_service

    try:
        async with await _client() as client:
            response = await client.post(
                f"/api/v1/assessments/{assessment.id}/review",
                json={"decision": "approved", "reviewer_name": "Dr. Smith"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
    finally:
        await _clear_overrides()
