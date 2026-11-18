"""Unit tests for the Moodle course-content retrieval service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from app.core.exceptions import CourseNotFound, LessonNotFound, MoodleIntegrationError
from app.db.repositories.courses import CourseRepository
from app.db.repositories.lessons import LessonRepository
from app.models.course import Course, CourseStatus
from app.models.lesson import Lesson, LessonStatus
from app.services.course_content.render import render_lesson_html
from app.services.moodle.client import MoodleClient
from app.services.moodle.content import MoodleCourseContentService
from app.services.moodle.mapper import lesson_id_marker

COURSE_ID = uuid.uuid4()
CURRICULUM_ID = uuid.uuid4()
LESSON_ID = uuid.uuid4()
MOODLE_COURSE_ID = 11


def _course(**overrides) -> Course:
    now = datetime.now(UTC)
    data = dict(
        id=COURSE_ID,
        curriculum_id=CURRICULUM_ID,
        title="Biology 101",
        fullname="Biology 101",
        shortname="bio101",
        idnumber=f"ai-ece-{COURSE_ID}",
        moodle_course_id=MOODLE_COURSE_ID,
        moodle_url=f"https://moodle.example.com/course/view.php?id={MOODLE_COURSE_ID}",
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


def _contents(sections):
    return sections


def _make_service(
    course: Course | None,
    lesson: Lesson | None,
    contents,
    contents_error: Exception | None = None,
    publishable: list[Lesson] | None = None,
) -> MoodleCourseContentService:
    client = AsyncMock(spec=MoodleClient)
    if contents_error is not None:
        client.get_course_contents = AsyncMock(side_effect=contents_error)  # type: ignore[method-assign]
    else:
        client.get_course_contents = AsyncMock(return_value=contents)  # type: ignore[method-assign]
    course_repo = AsyncMock(spec=CourseRepository)
    course_repo.get_by_id = AsyncMock(return_value=course)  # type: ignore[method-assign]
    lesson_repo = AsyncMock(spec=LessonRepository)
    lesson_repo.get_by_id = AsyncMock(return_value=lesson)  # type: ignore[method-assign]
    lesson_repo.list_publishable_by_curriculum = AsyncMock(  # type: ignore[method-assign]
        return_value=publishable or []
    )
    return MoodleCourseContentService(client, course_repo, lesson_repo)


def _page_section(*pages: dict) -> list[dict]:
    """One Moodle section holding the given page module dicts."""
    modules = [
        {
            "id": page["cmid"],
            "name": page["name"],
            "modname": "page",
            "contents": (
                [{"content": page["content"], "contentformat": 1}]
                if page.get("content") is not None
                else []
            ),
            "url": f"https://moodle.example.com/mod/page/view.php?id={page['cmid']}",
        }
        for page in pages
    ]
    return [{"section": 1, "name": "Week 1", "summary": "", "modules": modules}]


SECTIONS = [
    {
        "section": 1,
        "name": "Week 1",
        "summary": "First week.",
        "modules": [
            {
                "id": 101,
                "name": "Cell structure",
                "modname": "page",
                "contents": [{"content": "<p>Cell content.</p>", "contentformat": 1}],
                "url": "https://moodle.example.com/mod/page/view.php?id=101",
            }
        ],
    },
    {
        "section": 2,
        "name": "Week 2",
        "summary": "Second week.",
        "modules": [],
    },
]


class TestMoodleCourseContentService:
    @pytest.mark.anyio
    async def test_get_course_structure_returns_sections_and_modules(self):
        service = _make_service(_course(), None, SECTIONS)

        structure = await service.get_course_structure(COURSE_ID)

        assert structure.course_id == COURSE_ID
        assert structure.moodle_course_id == MOODLE_COURSE_ID
        assert structure.title == "Biology 101"
        assert structure.moodle_url == _course().moodle_url
        assert [s.section_number for s in structure.sections] == [1, 2]
        week1 = structure.sections[0]
        assert week1.name == "Week 1"
        assert len(week1.modules) == 1
        module = week1.modules[0]
        assert module.cmid == 101
        assert module.name == "Cell structure"
        assert module.modname == "page"
        assert module.content == "<p>Cell content.</p>"
        assert module.content_format == 1
        assert module.url.endswith("id=101")
        week2 = structure.sections[1]
        assert week2.modules == []
        service._client.get_course_contents.assert_awaited_once_with(MOODLE_COURSE_ID)

    @pytest.mark.anyio
    async def test_get_course_structure_course_not_found(self):
        service = _make_service(None, None, SECTIONS)

        with pytest.raises(CourseNotFound) as exc_info:
            await service.get_course_structure(COURSE_ID)
        assert exc_info.value.error_code == "course_not_found"

    @pytest.mark.anyio
    async def test_get_course_structure_not_published(self):
        service = _make_service(
            _course(moodle_course_id=None, moodle_url=None), None, SECTIONS
        )

        with pytest.raises(MoodleIntegrationError) as exc_info:
            await service.get_course_structure(COURSE_ID)
        assert exc_info.value.error_code == "moodle_integration_error"

    @pytest.mark.anyio
    async def test_get_course_structure_moodle_failure_is_a_clear_error(self):
        service = _make_service(
            _course(),
            None,
            SECTIONS,
            contents_error=MoodleIntegrationError("down"),
        )

        with pytest.raises(MoodleIntegrationError, match="down"):
            await service.get_course_structure(COURSE_ID)

    @pytest.mark.anyio
    async def test_get_lesson_content_returns_published_page_html(self):
        service = _make_service(_course(), _lesson(), SECTIONS)

        content = await service.get_lesson_content(COURSE_ID, LESSON_ID)

        assert content.course_id == COURSE_ID
        assert content.lesson_id == LESSON_ID
        assert content.title == "Cell structure"
        assert content.content_html == "<p>Cell content.</p>"
        assert content.content_format == 1

    @pytest.mark.anyio
    async def test_get_lesson_content_lesson_not_found(self):
        service = _make_service(_course(), None, SECTIONS)

        with pytest.raises(LessonNotFound) as exc_info:
            await service.get_lesson_content(COURSE_ID, LESSON_ID)
        assert exc_info.value.error_code == "lesson_not_found"

    @pytest.mark.anyio
    async def test_get_lesson_content_wrong_curriculum(self):
        service = _make_service(
            _course(), _lesson(curriculum_id=uuid.uuid4()), SECTIONS
        )

        with pytest.raises(LessonNotFound):
            await service.get_lesson_content(COURSE_ID, LESSON_ID)

    @pytest.mark.anyio
    async def test_get_lesson_content_not_published_to_moodle(self):
        service = _make_service(
            _course(), _lesson(), [{"section": 1, "name": "Week 1", "modules": []}]
        )

        with pytest.raises(LessonNotFound) as exc_info:
            await service.get_lesson_content(COURSE_ID, LESSON_ID)
        assert exc_info.value.error_code == "lesson_not_found"
        assert exc_info.value.details["lesson_title"] == "Cell structure"
        assert "Re-publish" in exc_info.value.message

    @pytest.mark.anyio
    async def test_get_lesson_content_moodle_failure_is_a_clear_error(self):
        service = _make_service(
            _course(),
            _lesson(),
            SECTIONS,
            contents_error=MoodleIntegrationError("down"),
        )

        with pytest.raises(MoodleIntegrationError, match="down"):
            await service.get_lesson_content(COURSE_ID, LESSON_ID)


class TestLessonContentResolution:
    """Resolution of a lesson to exactly its own published page."""

    def _two_same_title_lessons(self) -> tuple[Lesson, Lesson]:
        first = _lesson()
        second = _lesson(
            id=uuid.uuid4(),
            order_index=1,
            description="Cells and organelles, part two.",
        )
        return first, second

    @pytest.mark.anyio
    async def test_resolves_by_identity_marker_when_titles_duplicate(self):
        first, second = self._two_same_title_lessons()
        sections = _page_section(
            {
                "cmid": 201,
                "name": "Cell structure",
                "content": f"{lesson_id_marker(first.id)}\n<p>First page.</p>",
            },
            {
                "cmid": 202,
                "name": "Cell structure",
                "content": f"{lesson_id_marker(second.id)}\n<p>Second page.</p>",
            },
        )

        cases = (
            (first, "<p>First page.</p>"),
            (second, "<p>Second page.</p>"),
        )
        for lesson, expected in cases:
            service = _make_service(
                _course(), lesson, sections, publishable=[first, second]
            )
            content = await service.get_lesson_content(COURSE_ID, lesson.id)
            assert content.content_html == expected
            assert "skillup-lesson-id" not in content.content_html
            assert content.page_name == "Cell structure"

    @pytest.mark.anyio
    async def test_marker_beats_raw_title_match(self):
        lesson = _lesson()
        sections = _page_section(
            {
                "cmid": 301,
                "name": "Cell structure",
                "content": "<p>Some other lesson with the same title.</p>",
            },
            {
                "cmid": 302,
                "name": "Cell structure (renamed in Moodle)",
                "content": f"{lesson_id_marker(lesson.id)}\n<p>Renamed page body.</p>",
            },
        )

        service = _make_service(_course(), lesson, sections, publishable=[lesson])

        content = await service.get_lesson_content(COURSE_ID, lesson.id)

        assert content.content_html == "<p>Renamed page body.</p>"

    @pytest.mark.anyio
    async def test_reports_missing_page_body_instead_of_serving_empty_lesson(self):
        first, second = self._two_same_title_lessons()
        # A Moodle that does not return page content in core_course_get_contents
        # and does not expose mod_page_get_pages_by_courses: resolution by the
        # deterministic published page name still identifies the right page,
        # but the missing body must be reported, never rendered as empty.
        sections = _page_section(
            {"cmid": 401, "name": "Cell structure", "content": None},
            {"cmid": 402, "name": "Cell structure (Week 1)", "content": None},
        )

        for lesson, expected_cmid in ((first, 401), (second, 402)):
            service = _make_service(
                _course(), lesson, sections, publishable=[first, second]
            )
            with pytest.raises(MoodleIntegrationError) as exc_info:
                await service.get_lesson_content(COURSE_ID, lesson.id)
            assert exc_info.value.details["page_cmid"] == expected_cmid
            assert "mod_page_get_pages_by_courses" in exc_info.value.message

    @pytest.mark.anyio
    async def test_reads_page_bodies_through_mod_page_web_service(self):
        lesson = _lesson()
        # core_course_get_contents omits the body; the page-body service
        # supplies it, including the identity marker.
        sections = _page_section(
            {"cmid": 701, "name": "Cell structure", "content": None}
        )
        service = _make_service(_course(), lesson, sections, publishable=[lesson])
        service._client.get_pages_by_courses = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "pages": [
                    {
                        "coursemodule": 701,
                        "name": "Cell structure",
                        "content": f"{lesson_id_marker(lesson.id)}\n<p>Body.</p>",
                        "contentformat": 1,
                    }
                ]
            }
        )

        content = await service.get_lesson_content(COURSE_ID, lesson.id)

        assert content.content_html == "<p>Body.</p>"
        assert "skillup-lesson-id" not in content.content_html

    @pytest.mark.anyio
    async def test_course_structure_exposes_internal_lesson_ids(self):
        first, second = self._two_same_title_lessons()
        sections = _page_section(
            {
                "cmid": 801,
                "name": "Cell structure",
                "content": f"{lesson_id_marker(first.id)}\n<p>first</p>",
            },
            {"cmid": 802, "name": "Cell structure (Week 1)", "content": None},
        )
        service = _make_service(
            _course(), None, sections, publishable=[first, second]
        )

        structure = await service.get_course_structure(COURSE_ID)

        modules = structure.sections[0].modules
        assert modules[0].lesson_id == first.id
        assert modules[1].lesson_id == second.id

    @pytest.mark.anyio
    async def test_course_structure_leaves_unidentifiable_page_unresolved(self):
        lesson = _lesson()
        sections = _page_section(
            {"cmid": 901, "name": "Some unrelated page", "content": None}
        )
        service = _make_service(_course(), None, sections, publishable=[lesson])

        structure = await service.get_course_structure(COURSE_ID)

        assert structure.sections[0].modules[0].lesson_id is None

    @pytest.mark.anyio
    async def test_duplicate_title_resolved_by_content_equality_for_legacy_pages(self):
        lesson = _lesson()
        rendered = render_lesson_html(lesson)
        sections = _page_section(
            {"cmid": 501, "name": "Cell structure", "content": "<p>Other lesson.</p>"},
            {"cmid": 502, "name": "Cell structure", "content": rendered},
        )

        service = _make_service(_course(), lesson, sections, publishable=[lesson])

        content = await service.get_lesson_content(COURSE_ID, lesson.id)

        assert content.content_html == rendered
        assert content.page_name == "Cell structure"

    @pytest.mark.anyio
    async def test_ambiguous_duplicate_title_raises_clear_error(self):
        lesson = _lesson()
        sections = _page_section(
            {"cmid": 601, "name": "Cell structure", "content": "<p>A.</p>"},
            {"cmid": 602, "name": "Cell structure", "content": "<p>B.</p>"},
        )

        service = _make_service(_course(), lesson, sections, publishable=[lesson])

        with pytest.raises(LessonNotFound) as exc_info:
            await service.get_lesson_content(COURSE_ID, lesson.id)

        assert exc_info.value.error_code == "lesson_not_found"
        assert exc_info.value.details["matching_page_cmids"] == [601, 602]
        assert "cannot be told apart" in exc_info.value.message
