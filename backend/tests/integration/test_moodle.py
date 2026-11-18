"""Integration tests for Moodle course reads through a fake web-service client."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime

import pytest
from app.core.exceptions import MoodleIntegrationError
from app.models.course import Course, CourseStatus
from app.models.lesson import Lesson, LessonStatus
from app.services.moodle.content import MoodleCourseContentService
from app.services.moodle.mapper import lesson_id_marker

COURSE_ID = uuid.uuid4()
CURRICULUM_ID = uuid.uuid4()
MOODLE_COURSE_ID = 11


def _course() -> Course:
    now = datetime.now(UTC)
    return Course(
        id=COURSE_ID,
        curriculum_id=CURRICULUM_ID,
        title="Networking 101",
        fullname="Networking 101",
        shortname="net101",
        idnumber=f"ai-ece-{COURSE_ID}",
        moodle_course_id=MOODLE_COURSE_ID,
        moodle_url=f"https://moodle.example.com/course/view.php?id={MOODLE_COURSE_ID}",
        status=CourseStatus.SYNCED,
        sections_published=2,
        resources_published=2,
        last_sync_at=now,
        created_at=now,
        updated_at=now,
    )


def _lesson(**overrides) -> Lesson:
    data = dict(
        id=uuid.uuid4(),
        curriculum_id=CURRICULUM_ID,
        curriculum_unit_id=uuid.uuid4(),
        week_number=1,
        order_index=0,
        title="DNS basics",
        description="How names become addresses.",
        learning_objectives=["Trace a lookup."],
        estimated_workload_minutes=45,
        status=LessonStatus.APPROVED,
        generation_errors=[],
    )
    data.update(overrides)
    lesson = Lesson(**data)
    lesson.content_blocks = []
    return lesson


def _page_section(*pages: tuple[int, str, str | None]) -> list[dict]:
    """Build core_course_get_contents sections from (cmid, name, body) tuples."""
    return [
        {
            "section": index + 1,
            "name": f"Week {index + 1}",
            "summary": "",
            "modules": [
                {
                    "id": cmid,
                    "name": name,
                    "modname": "page",
                    "contents": (
                        [{"content": body, "contentformat": 1}] if body else []
                    ),
                    "url": f"https://moodle.example.com/mod/page/view.php?id={cmid}",
                }
            ],
        }
        for index, (cmid, name, body) in enumerate(pages)
    ]


class _FakeMoodleClient:
    def __init__(self, sections: list[dict], pages: list[dict] | None = None) -> None:
        self.sections = sections
        self.pages = pages or []
        self.calls: list[tuple[str, int]] = []

    async def get_course_contents(self, moodle_course_id: int) -> list[dict]:
        self.calls.append(("contents", moodle_course_id))
        return deepcopy(self.sections)

    async def get_pages_by_courses(self, moodle_course_id: int) -> dict:
        self.calls.append(("pages", moodle_course_id))
        return {"pages": deepcopy(self.pages)}


class _CourseRepository:
    def __init__(self, course: Course) -> None:
        self.course = course

    async def get_by_id(self, course_id: uuid.UUID) -> Course | None:
        return self.course


class _LessonRepository:
    def __init__(self, lessons: list[Lesson]) -> None:
        self.lessons = lessons

    async def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        return next((lesson for lesson in self.lessons if lesson.id == lesson_id), None)

    async def list_publishable_by_curriculum(
        self, curriculum_id: uuid.UUID
    ) -> list[Lesson]:
        return self.lessons


def _service(
    sections: list[dict], lessons: list[Lesson], pages: list[dict] | None = None
) -> tuple[MoodleCourseContentService, _FakeMoodleClient]:
    client = _FakeMoodleClient(sections, pages)
    return (
        MoodleCourseContentService(
            client, _CourseRepository(_course()), _LessonRepository(lessons)
        ),
        client,
    )


async def test_course_structure_maps_sections_and_internal_lesson_ids() -> None:
    """Published pages resolve back to lessons via marker or unique page name."""
    first = _lesson()
    second = _lesson(order_index=1, description="A second, different lesson.")
    sections = _page_section(
        (
            101,
            "DNS basics",
            f"{lesson_id_marker(first.id)}\n<p>First page.</p>",
        ),
        (102, "DNS basics (Week 1)", None),
    )
    service, client = _service(sections, [first, second])

    structure = await service.get_course_structure(COURSE_ID)

    assert structure.course_id == COURSE_ID
    assert structure.moodle_course_id == MOODLE_COURSE_ID
    assert [section.section_number for section in structure.sections] == [1, 2]
    assert [section.name for section in structure.sections] == ["Week 1", "Week 2"]
    modules = [module for section in structure.sections for module in section.modules]
    assert [(module.cmid, module.name, module.modname) for module in modules] == [
        (101, "DNS basics", "page"),
        (102, "DNS basics (Week 1)", "page"),
    ]
    assert [module.lesson_id for module in modules] == [first.id, second.id]
    assert modules[0].content == f"{lesson_id_marker(first.id)}\n<p>First page.</p>"
    assert modules[0].url.endswith("id=101")
    assert client.calls == [("contents", MOODLE_COURSE_ID)]


async def test_lesson_content_is_read_from_the_moodle_page_body_service() -> None:
    """core_course_get_contents lacks bodies; the page service supplies them."""
    lesson = _lesson()
    sections = _page_section((201, "DNS basics", None))
    pages = [
        {
            "coursemodule": 201,
            "name": "DNS basics",
            "content": f"{lesson_id_marker(lesson.id)}\n<p>Body from Moodle.</p>",
            "contentformat": 1,
        }
    ]
    service, client = _service(sections, [lesson], pages)

    content = await service.get_lesson_content(COURSE_ID, lesson.id)

    assert content.course_id == COURSE_ID
    assert content.lesson_id == lesson.id
    assert content.title == "DNS basics"
    assert content.page_name == "DNS basics"
    assert content.content_html == "<p>Body from Moodle.</p>"
    assert content.content_format == 1
    assert client.calls == [
        ("contents", MOODLE_COURSE_ID),
        ("pages", MOODLE_COURSE_ID),
    ]


async def test_lesson_content_reports_a_missing_moodle_page_body() -> None:
    """A resolved page without a body must fail instead of serving nothing."""
    lesson = _lesson()
    sections = _page_section((301, "DNS basics", None))
    service, client = _service(sections, [lesson])

    with pytest.raises(MoodleIntegrationError) as exc_info:
        await service.get_lesson_content(COURSE_ID, lesson.id)

    assert "mod_page_get_pages_by_courses" in exc_info.value.message
    assert exc_info.value.details["page_cmid"] == 301
    assert exc_info.value.details["lesson_id"] == str(lesson.id)
    assert ("pages", MOODLE_COURSE_ID) in client.calls
