"""Route-level tests for final assessments and certificates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from app.api.v1.learner import get_learner_assessment_service
from app.core.dependencies import get_database_session
from app.db.repositories.certificates import CertificateRepository
from app.main import create_application
from app.models.certificate import Certificate
from app.models.user import UserRole
from app.schemas.learner_assessment import (
    AssessmentAttemptRead,
    AssessmentItemResult,
    AssessmentQuestionRead,
    CertificateCourseRead,
    FinalAssessmentRead,
)
from httpx import ASGITransport, AsyncClient
from tests.helpers import FakeRedis, install_auth_override

ASSESSMENT_ID = uuid.uuid4()
COURSE_ID = uuid.uuid4()
ATTEMPT_ID = uuid.uuid4()
REFERENCE = "SKU-2026-ABCDEF123456"


def _attempt() -> AssessmentAttemptRead:
    return AssessmentAttemptRead(
        id=ATTEMPT_ID,
        assessment_id=ASSESSMENT_ID,
        attempt_number=1,
        score_percent=100,
        correct_count=3,
        auto_gradable_count=3,
        passed=True,
        submitted_at=datetime.now(UTC),
        results=[
            AssessmentItemResult(
                item_index=0,
                kind="multiple_choice",
                prompt="Which record keeps stock counts?",
                answered=True,
                auto_graded=True,
                correct=True,
                submitted_option_id="a",
                correct_option_id="a",
                correct_answer="Inventory ledger",
                explanation="An inventory ledger records stock movements.",
            )
        ],
    )


def _certificate() -> CertificateCourseRead:
    return CertificateCourseRead(
        reference=REFERENCE,
        learner_name="Test User",
        course_title="Introduction to Agribusiness",
        score_percent=100,
        completed_lessons=4,
        total_lessons=4,
        issued_at=datetime.now(UTC),
        course_id=COURSE_ID,
    )


class FakeLearnerAssessmentService:
    async def get_final_assessment(self, user, course_id):
        return FinalAssessmentRead(
            assessment_id=ASSESSMENT_ID,
            title="Final assessment",
            description="Covers the whole course.",
            estimated_minutes=60,
            pass_percent=70,
            questions=[
                AssessmentQuestionRead(
                    item_index=0,
                    kind="multiple_choice",
                    prompt="Which record keeps stock counts?",
                    learning_objective="Track inventory",
                    difficulty="easy",
                    options=[
                        {"id": "a", "text": "Inventory ledger"},
                        {"id": "b", "text": "Payroll sheet"},
                    ],
                    auto_gradable=True,
                )
            ],
            auto_gradable_count=3,
            total_items=4,
            completed_lessons=4,
            total_lessons=4,
            all_lessons_completed=True,
            attempts=[],
            best_score_percent=None,
            best_attempt_id=None,
            passed=False,
            certificate=None,
        )

    async def submit_attempt(self, user, course_id, payload):
        return _attempt()

    async def list_attempts(self, user, course_id):
        return [await self.submit_attempt(user, course_id, None)]

    async def issue_certificate(self, user, course_id):
        return _certificate()

    async def list_certificates(self, user):
        return [_certificate()]


def _application():
    application = create_application()
    application.state.redis_client = FakeRedis()
    install_auth_override(application, role=UserRole.STUDENT)
    service = FakeLearnerAssessmentService()
    application.dependency_overrides[get_learner_assessment_service] = lambda: service
    return application


@pytest.mark.asyncio
async def test_final_assessment_payload_never_contains_answers():
    application = _application()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get(
            f"/api/v1/learner/courses/{COURSE_ID}/final-assessment"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["pass_percent"] == 70
    assert body["questions"][0]["options"][0]["text"] == "Inventory ledger"
    assert "correct_option_id" not in body["questions"][0]
    assert "correct_answer" not in body["questions"][0]
    assert "explanation" not in body["questions"][0]


@pytest.mark.asyncio
async def test_submit_attempt_returns_feedback():
    application = _application()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"/api/v1/learner/courses/{COURSE_ID}/final-assessment/attempts",
            json={"answers": [{"item_index": 0, "option_id": "a"}]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["score_percent"] == 100
    assert body["results"][0]["correct_answer"] == "Inventory ledger"


@pytest.mark.asyncio
async def test_attempt_history_and_certificate_endpoints():
    application = _application()
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        history = await client.get(
            f"/api/v1/learner/courses/{COURSE_ID}/final-assessment/attempts"
        )
        cert = await client.post(f"/api/v1/learner/courses/{COURSE_ID}/certificate")
        owned = await client.get("/api/v1/learner/certificates")

    assert history.status_code == 200
    assert history.json()["attempts"][0]["attempt_number"] == 1
    assert cert.status_code == 200
    assert cert.json()["reference"] == REFERENCE
    assert owned.status_code == 200
    assert owned.json()["certificates"][0]["reference"] == REFERENCE


@pytest.mark.asyncio
async def test_public_verification_needs_no_session(monkeypatch):
    certificate = Certificate(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        course_id=COURSE_ID,
        enrolment_id=uuid.uuid4(),
        assessment_id=ASSESSMENT_ID,
        attempt_id=ATTEMPT_ID,
        reference=REFERENCE,
        learner_name="Test User",
        course_title="Introduction to Agribusiness",
        score_percent=100,
        completed_lessons=4,
        total_lessons=4,
        issued_at=datetime.now(UTC),
    )

    async def _get_by_reference(self, reference):
        return certificate if reference == REFERENCE else None

    async def _session():
        yield None

    monkeypatch.setattr(CertificateRepository, "get_by_reference", _get_by_reference)
    application = create_application()
    application.dependency_overrides[get_database_session] = _session

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        found = await client.get(f"/api/v1/certificates/verify/{REFERENCE}")
        missing = await client.get("/api/v1/certificates/verify/SKU-2026-NOPE")

    assert found.status_code == 200
    assert found.json()["reference"] == REFERENCE
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "certificate_not_found"
