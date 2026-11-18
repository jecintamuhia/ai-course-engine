"""Route-level tests for the learner portal endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from app.api.v1.learner import get_learner_portal_service
from app.core.dependencies import get_current_user
from app.core.exceptions import NotEnrolledError
from app.main import create_application
from app.models.course import Course, CourseStatus
from app.models.learner_enrolment import EnrolmentStatus, LearnerEnrolment
from app.models.learner_milestone import LearnerMilestone
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from app.models.practical_submission import PracticalSubmission, SubmissionStatus
from app.models.user import UserRole
from httpx import ASGITransport, AsyncClient
from tests.helpers import install_auth_override, make_test_user

PROFILE_URL = "/api/v1/learner/profile"
COURSES_URL = "/api/v1/learner/courses"
CATALOG_URL = "/api/v1/learner/catalog"


def _course(
    *,
    title: str = "Intro to Statistics",
    status: CourseStatus = CourseStatus.SYNCED,
    moodle_url: str
    | None = "https://elearning.skillupafrica.co.ke/course/view.php?id=7",
) -> Course:
    now = datetime.now(UTC)
    return Course(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        title=title,
        fullname=title,
        shortname=title[:20],
        idnumber=f"ai-ece-{uuid.uuid4()}",
        moodle_course_id=7,
        moodle_url=moodle_url,
        status=status,
        sections_published=4,
        resources_published=12,
        last_sync_at=now,
        sync_error=None,
        created_at=now,
        updated_at=now,
    )


def _lesson(course: Course) -> Lesson:
    now = datetime.now(UTC)
    lesson = Lesson(
        id=uuid.uuid4(),
        curriculum_id=course.curriculum_id,
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="Describing Data",
        description="How to describe a dataset.",
        learning_objectives=["Summarise a dataset."],
        estimated_workload_minutes=45,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    lesson.created_at = now
    lesson.updated_at = now
    block = LessonContentBlock(
        id=uuid.uuid4(),
        lesson_id=lesson.id,
        block_type=LessonBlockType.PRACTICAL_TASK,
        order_index=0,
        title="Practical task",
        payload={"prompt": "Summarise the data."},
        review_status=BlockReviewStatus.APPROVED,
    )
    block.created_at = now
    block.updated_at = now
    lesson.content_blocks = [block]
    return lesson


def _submission(enrolment_id: uuid.UUID, block_id: uuid.UUID) -> PracticalSubmission:
    now = datetime.now(UTC)
    return PracticalSubmission(
        id=uuid.uuid4(),
        enrolment_id=enrolment_id,
        block_id=block_id,
        lesson_id=uuid.uuid4(),
        content="# My answer",
        status=SubmissionStatus.GRADED,
        grade=80,
        feedback="Solid work.",
        submitted_at=now,
        graded_at=now,
        graded_by_id=uuid.uuid4(),
    )


class _FakeLearnerService:
    """Stand-in for the learner portal service."""

    def __init__(self) -> None:
        self.course = _course()
        self.lesson = _lesson(self.course)
        self.enrolment = LearnerEnrolment(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            course_id=self.course.id,
            status=EnrolmentStatus.ACTIVE,
        )
        self.submission = _submission(
            self.enrolment.id, self.lesson.content_blocks[0].id
        )
        self.milestone = LearnerMilestone(
            id=uuid.uuid4(),
            enrolment_id=self.enrolment.id,
            lesson_id=self.lesson.id,
            completed_at=datetime.now(UTC),
        )
        self.enrolled = True
        self.completed = False

    async def list_catalog(self) -> list[Course]:
        return [self.course]

    async def list_enrolled_courses(self, user) -> list[Course]:
        return [self.course] if self.enrolled else []

    async def enrol(self, user, course_id: uuid.UUID) -> LearnerEnrolment:
        self.enrolled = True
        return self.enrolment

    async def withdraw(self, user, course_id: uuid.UUID) -> LearnerEnrolment:
        self.enrolled = False
        return self.enrolment

    async def get_course_detail(self, user, course_id: uuid.UUID):
        if not self.enrolled:
            raise NotEnrolledError("Enrol in this course to view its content.")
        submissions = {self.submission.block_id: self.submission}
        milestones = [self.milestone] if self.completed else []
        return self.course, [self.lesson], milestones, submissions

    async def complete_lesson(self, user, course_id, lesson_id) -> LearnerMilestone:
        self.completed = True
        return self.milestone

    async def undo_lesson_completion(self, user, course_id, lesson_id) -> bool:
        self.completed = False
        return True

    async def submit_practical_task(self, user, course_id, block_id, content):
        self.submission.content = content
        self.submission.status = SubmissionStatus.SUBMITTED
        return self.submission

    async def list_my_submissions(self, user) -> list[PracticalSubmission]:
        return [self.submission]


def _build_client(fake: _FakeLearnerService, *, role: UserRole = UserRole.STUDENT):
    application = create_application()
    install_auth_override(application, role=role)
    application.dependency_overrides[get_learner_portal_service] = lambda: fake
    return application


async def test_profile_returns_the_callers_own_account(
    client: httpx.AsyncClient,
) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: make_test_user(
        role=UserRole.STUDENT,
        email="learner@example.com",
    )

    response = await client.get(PROFILE_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "learner@example.com"
    assert body["role"] == "student"


async def test_profile_requires_authentication() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(PROFILE_URL)

    assert response.status_code == 401


async def test_courses_lists_enrolled_courses() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(COURSES_URL)

    assert response.status_code == 200
    courses = response.json()["courses"]
    assert len(courses) == 1
    assert courses[0]["title"] == "Intro to Statistics"
    assert courses[0]["moodle_url"] == fake.course.moodle_url
    assert courses[0]["sections_published"] == 4
    assert courses[0]["resources_published"] == 12


async def test_courses_are_empty_when_not_enrolled() -> None:
    fake = _FakeLearnerService()
    fake.enrolled = False
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(COURSES_URL)

    assert response.status_code == 200
    assert response.json()["courses"] == []


async def test_catalog_lists_published_courses() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(CATALOG_URL)

    assert response.status_code == 200
    assert len(response.json()["courses"]) == 1


async def test_courses_require_authentication() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(COURSES_URL)

    assert response.status_code == 401


async def test_enrol_returns_the_enrolment_id() -> None:
    fake = _FakeLearnerService()
    fake.enrolled = False
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(f"{COURSES_URL}/{fake.course.id}/enrol")

    assert response.status_code == 200
    assert response.json()["enrolled"] is True
    assert response.json()["enrolment_id"] == str(fake.enrolment.id)


async def test_withdraw_reports_the_caller_left_the_course() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(f"{COURSES_URL}/{fake.course.id}/enrol")

    assert response.status_code == 200
    assert response.json()["enrolled"] is False


async def test_course_detail_reports_progress() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"{COURSES_URL}/{fake.course.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["course"]["title"] == "Intro to Statistics"
    assert body["progress"]["total_lessons"] == 1
    assert body["progress"]["percentage"] == 0
    assert body["lessons"][0]["blocks"][0]["block_type"] == "practical_task"


async def test_course_detail_includes_the_callers_submission() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"{COURSES_URL}/{fake.course.id}")

    block = response.json()["lessons"][0]["blocks"][0]
    assert block["submission"]["status"] == "graded"
    assert block["submission"]["grade"] == 80


async def test_course_detail_is_refused_without_enrolment() -> None:
    fake = _FakeLearnerService()
    fake.enrolled = False
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"{COURSES_URL}/{fake.course.id}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_enrolled"


async def test_completing_a_lesson_is_idempotent() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"{COURSES_URL}/{fake.course.id}/lessons/{fake.lesson.id}/complete"
        )

    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert response.json()["milestone_id"] == str(fake.milestone.id)


async def test_uncompleting_a_lesson_clears_the_milestone() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.delete(
            f"{COURSES_URL}/{fake.course.id}/lessons/{fake.lesson.id}/complete"
        )

    assert response.status_code == 200
    assert response.json()["completed"] is False


async def test_submitting_a_practical_task_records_the_content() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)
    block_id = fake.lesson.content_blocks[0].id

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"{COURSES_URL}/{fake.course.id}/blocks/{block_id}/submit",
            json={"content": "# Revised answer"},
        )

    assert response.status_code == 200
    body = response.json()["submission"]
    assert body["content"] == "# Revised answer"
    assert body["status"] == "submitted"


async def test_submission_requires_content() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)
    block_id = fake.lesson.content_blocks[0].id

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"{COURSES_URL}/{fake.course.id}/blocks/{block_id}/submit",
            json={"content": ""},
        )

    assert response.status_code == 422


async def test_listing_my_submissions() -> None:
    fake = _FakeLearnerService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/learner/submissions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["grade"] == 80


async def test_staff_may_preview_the_learner_portal(
    client: httpx.AsyncClient,
) -> None:
    """A lecturer can open the portal to see what a learner sees."""
    install_auth_override(client.app, role=UserRole.LECTURER)
    client.app.dependency_overrides[get_learner_portal_service] = lambda: (
        _FakeLearnerService()
    )

    response = await client.get(COURSES_URL)

    assert response.status_code == 200


def test_require_learner_admits_learners_and_staff() -> None:
    from app.core.dependencies import require_learner

    for role in (
        UserRole.STUDENT,
        UserRole.TEACHER,
        UserRole.LECTURER,
        UserRole.ADMIN,
    ):
        user = make_test_user(role=role)
        assert require_learner(user) is user


def test_require_staff_still_rejects_learners() -> None:
    from app.core.dependencies import require_staff
    from app.core.exceptions import AuthorizationError

    for role in (UserRole.STUDENT, UserRole.TEACHER):
        with pytest.raises(AuthorizationError):
            require_staff(make_test_user(role=role))
