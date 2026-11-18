"""Route-level tests for the lecturer review endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.v1.lecturer import get_lecturer_review_service
from app.core.exceptions import PracticalSubmissionNotFound
from app.main import create_application
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import UserRole
from httpx import ASGITransport, AsyncClient
from tests.helpers import install_auth_override


class _FakeLecturerService:
    """Stand-in for the lecturer review service."""

    def __init__(self) -> None:
        self.course_id = uuid.uuid4()
        now = datetime.now(UTC)
        self.submission = PracticalSubmission(
            id=uuid.uuid4(),
            enrolment_id=uuid.uuid4(),
            block_id=uuid.uuid4(),
            lesson_id=uuid.uuid4(),
            content="# My answer",
            status=SubmissionStatus.SUBMITTED,
            grade=None,
            feedback=None,
            submitted_at=now,
            graded_at=None,
            graded_by_id=None,
        )

    async def list_submissions(self, course_id: uuid.UUID) -> list[dict]:
        return [
            {
                "id": self.submission.id,
                "enrolment_id": self.submission.enrolment_id,
                "block_id": self.submission.block_id,
                "lesson_id": self.submission.lesson_id,
                "content": self.submission.content,
                "status": self.submission.status,
                "grade": self.submission.grade,
                "feedback": self.submission.feedback,
                "submitted_at": self.submission.submitted_at,
                "graded_at": self.submission.graded_at,
                "graded_by_id": self.submission.graded_by_id,
            }
        ]

    async def list_pending_submissions(self, course_id: uuid.UUID) -> list[dict]:
        return await self.list_submissions(course_id)

    async def list_activities(self, course_id: uuid.UUID, limit: int = 50) -> list:
        return []

    async def list_learner_progress(self, course_id: uuid.UUID) -> list[dict]:
        return [
            {
                "enrolment_id": uuid.uuid4(),
                "user_id": uuid.uuid4(),
                "full_name": "Ada Learner",
                "email": "ada@example.com",
                "enrolled_at": datetime.now(UTC),
                "completed_lessons": 3,
                "total_lessons": 4,
                "percentage": 75,
                "submission_count": 1,
            }
        ]

    async def grade_submission(
        self,
        submission_id: uuid.UUID,
        grader,
        grade: int | None,
        feedback: str | None,
    ) -> PracticalSubmission:
        if submission_id != self.submission.id:
            raise PracticalSubmissionNotFound("Submission not found.")
        self.submission.status = SubmissionStatus.GRADED
        self.submission.grade = grade
        self.submission.feedback = feedback
        self.submission.graded_at = datetime.now(UTC)
        return self.submission

    async def return_submission(
        self,
        submission_id: uuid.UUID,
        grader,
        feedback: str | None,
    ) -> PracticalSubmission:
        if submission_id != self.submission.id:
            raise PracticalSubmissionNotFound("Submission not found.")
        self.submission.status = SubmissionStatus.NEEDS_REVISION
        self.submission.feedback = feedback
        return self.submission


def _build_client(fake: _FakeLecturerService, *, role: UserRole = UserRole.LECTURER):
    application = create_application()
    install_auth_override(application, role=role)
    application.dependency_overrides[get_lecturer_review_service] = lambda: fake
    return application


async def test_list_submissions_for_a_course() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/lecturer/courses/{fake.course_id}/submissions"
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["content"] == "# My answer"
    assert body[0]["status"] == "submitted"


async def test_list_learner_progress() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/lecturer/courses/{fake.course_id}/learners"
        )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["full_name"] == "Ada Learner"
    assert body[0]["percentage"] == 75


async def test_grading_a_submission_stores_the_mark() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/api/v1/lecturer/submissions/{fake.submission.id}/grade",
            json={"grade": 85, "feedback": "Good work"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "graded"
    assert body["grade"] == 85
    assert body["feedback"] == "Good work"


async def test_returning_a_submission_asks_for_revision() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/api/v1/lecturer/submissions/{fake.submission.id}/return",
            json={"feedback": "Add more detail"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_revision"
    assert body["feedback"] == "Add more detail"


async def test_grading_rejects_an_out_of_range_mark() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/api/v1/lecturer/submissions/{fake.submission.id}/grade",
            json={"grade": 140},
        )

    assert response.status_code == 422


async def test_lecturer_routes_are_closed_to_learners() -> None:
    fake = _FakeLecturerService()
    application = _build_client(fake, role=UserRole.STUDENT)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/lecturer/courses/{fake.course_id}/learners"
        )

    assert response.status_code == 403


async def test_lecturer_routes_require_authentication() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(f"/api/v1/lecturer/courses/{uuid.uuid4()}/learners")

    assert response.status_code == 401
