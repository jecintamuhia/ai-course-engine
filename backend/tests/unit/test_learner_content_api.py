"""Route-level tests for the learner Moodle course-content endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.v1.learner import get_learner_portal_service
from app.core.dependencies import get_moodle_content_service
from app.core.exceptions import NotEnrolledError
from app.main import create_application
from app.models.course import Course, CourseStatus
from app.models.lesson import Lesson, LessonStatus
from app.models.user import UserRole
from httpx import ASGITransport, AsyncClient
from tests.helpers import install_auth_override, make_test_user

COURSE_CONTENT_URL = "/api/v1/learner/courses/{course_id}/content"
LESSON_CONTENT_URL = "/api/v1/learner/courses/{course_id}/lessons/{lesson_id}/content"

COURSE_ID = uuid.uuid4()
LESSON_ID = uuid.uuid4()
CURRICULUM_ID = uuid.uuid4()


def _course(**overrides) -> Course:
    now = datetime.now(UTC)
    data = dict(
        id=COURSE_ID,
        curriculum_id=CURRICULUM_ID,
        title="Biology 101",
        fullname="Biology 101",
        shortname="bio101",
        idnumber=f"ai-ece-{COURSE_ID}",
        moodle_course_id=7,
        moodle_url="https://elearning.skillupafrica.co.ke/course/view.php?id=7",
        status=CourseStatus.SYNCED,
        sections_published=2,
        resources_published=2,
        last_sync_at=now,
        sync_error=None,
        created_at=now,
        updated_at=now,
    )
    data.update(overrides)
    return Course(**data)


def _lesson(**overrides) -> Lesson:
    data = dict(
        id=LESSON_ID,
        curriculum_id=CURRICULUM_ID,
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="Cell structure",
        description="Cells and organelles.",
        learning_objectives=["Identify organelles."],
        estimated_workload_minutes=45,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    data.update(overrides)
    lesson = Lesson(**data)
    lesson.created_at = datetime.now(UTC)
    lesson.updated_at = datetime.now(UTC)
    return lesson


def _structure_payload() -> dict:
    return {
        "course_id": str(COURSE_ID),
        "moodle_course_id": 7,
        "moodle_url": "https://elearning.skillupafrica.co.ke/course/view.php?id=7",
        "title": "Biology 101",
        "fullname": "Biology 101",
        "shortname": "bio101",
        "sections": [
            {
                "section_number": 1,
                "name": "Week 1",
                "summary": "First week.",
                "modules": [
                    {
                        "cmid": 101,
                        "name": "Cell structure",
                        "modname": "page",
                        "content": "<p>Cell content.</p>",
                        "content_format": 1,
                        "url": "https://elearning.skillupafrica.co.ke/mod/page/view.php?id=101",
                    }
                ],
            }
        ],
    }


def _lesson_content_payload() -> dict:
    return {
        "course_id": str(COURSE_ID),
        "lesson_id": str(LESSON_ID),
        "title": "Cell structure",
        "content_html": "<p>Cell content.</p>",
        "content_format": 1,
    }


class _FakeLearnerService:
    def __init__(self, *, enrolled: bool = True):
        self.enrolled = enrolled
        self.course = _course()

    async def require_enrolment(self, user, course_id: uuid.UUID) -> None:
        if not self.enrolled:
            raise NotEnrolledError("Enrol in this course to view its content.")
        if course_id != self.course.id:
            from app.core.exceptions import CourseNotFound

            raise CourseNotFound("Course not found.")


class _FakeContentService:
    def __init__(self, *, structure=None, lesson=None):
        self.structure = structure
        self.lesson = lesson

    async def get_course_structure(self, course_id: uuid.UUID):
        if self.structure is None:
            from app.core.exceptions import CourseNotFound

            raise CourseNotFound("Course not found.")
        return self.structure

    async def get_lesson_content(self, course_id: uuid.UUID, lesson_id: uuid.UUID):
        if self.lesson is None:
            from app.core.exceptions import LessonNotFound

            raise LessonNotFound("Lesson not found.")
        return self.lesson


def _build_client(
    *,
    learner_service,
    content_service,
    role: UserRole = UserRole.STUDENT,
):
    application = create_application()
    install_auth_override(application, role=role)
    application.dependency_overrides[
        get_learner_portal_service
    ] = lambda: learner_service
    application.dependency_overrides[
        get_moodle_content_service
    ] = lambda: content_service
    return application


async def test_learner_course_content_returns_moodle_structure() -> None:
    fake_service = _FakeLearnerService(enrolled=True)
    content_service = _FakeContentService(structure=_structure_payload())
    application = _build_client(
        learner_service=fake_service, content_service=content_service
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(COURSE_CONTENT_URL.format(course_id=COURSE_ID))

    assert response.status_code == 200
    body = response.json()
    assert body["course_id"] == str(COURSE_ID)
    assert body["moodle_course_id"] == 7
    assert body["title"] == "Biology 101"
    assert len(body["sections"]) == 1
    module = body["sections"][0]["modules"][0]
    assert module["name"] == "Cell structure"
    assert module["modname"] == "page"
    assert module["content"] == "<p>Cell content.</p>"
    # No Moodle token leaks through.
    assert "wstoken" not in response.text.lower()


async def test_learner_lesson_content_returns_page_html() -> None:
    fake_service = _FakeLearnerService(enrolled=True)
    content_service = _FakeContentService(lesson=_lesson_content_payload())
    application = _build_client(
        learner_service=fake_service, content_service=content_service
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            LESSON_CONTENT_URL.format(course_id=COURSE_ID, lesson_id=LESSON_ID)
        )

    assert response.status_code == 200
    body = response.json()
    assert body["lesson_id"] == str(LESSON_ID)
    assert body["title"] == "Cell structure"
    assert body["content_html"] == "<p>Cell content.</p>"


async def test_course_content_requires_enrolment() -> None:
    fake_service = _FakeLearnerService(enrolled=False)
    content_service = _FakeContentService(structure=_structure_payload())
    application = _build_client(
        learner_service=fake_service, content_service=content_service
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(COURSE_CONTENT_URL.format(course_id=COURSE_ID))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_enrolled"


async def test_course_content_unknown_course() -> None:
    fake_service = _FakeLearnerService(enrolled=True)
    content_service = _FakeContentService(structure=None)
    application = _build_client(
        learner_service=fake_service, content_service=content_service
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(COURSE_CONTENT_URL.format(course_id=COURSE_ID))

    assert response.status_code == 404


async def test_lesson_content_not_published_to_moodle() -> None:
    fake_service = _FakeLearnerService(enrolled=True)
    content_service = _FakeContentService(lesson=None)
    application = _build_client(
        learner_service=fake_service, content_service=content_service
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            LESSON_CONTENT_URL.format(course_id=COURSE_ID, lesson_id=LESSON_ID)
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "lesson_not_found"


async def test_content_endpoints_require_authentication() -> None:
    application = create_application()

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as anon:
        response = await anon.get(COURSE_CONTENT_URL.format(course_id=COURSE_ID))

    assert response.status_code == 401


def test_lecturer_may_review_course_content() -> None:
    """Lecturer role can open the content service (staff-authorized route)."""
    from app.core.dependencies import require_staff

    user = make_test_user(role=UserRole.LECTURER)
    assert require_staff(user) is user
