"""Moodle course-content retrieval for the SkillUp Action Africa portals.

Resolves an internal course record (and its lessons) to the matching
published Moodle course and pulls the curriculum structure (sections and
their order, page modules) and the individual lesson page content back
through the configured Moodle web service token.

Only read-only web service calls are used: ``core_course_get_contents``,
which is already required for publishing verification and section/module
reading. No Moodle administrator credentials, privileged service token, or
secret configuration ever reaches the browser.

Lesson content is resolved to exactly the page the lesson was published
from, in this order:

1. the page's embedded lesson identity marker (see
   ``app.services.moodle.mapper.lesson_id_marker``);
2. the lesson's deterministic, course-wide unique published page name
   (see ``app.services.moodle.lessons.compute_lesson_page_names``);
3. for courses published before both mechanisms existed, a unique page
   matching the raw lesson title;
4. when several pages share the raw title, the single title-matching
   page whose content equals the lesson's rendered HTML.

Page bodies are resolved through ``mod_page_get_pages_by_courses``
because ``core_course_get_contents`` returns page *files*, not the page
body. If a body cannot be read the service raises a clear, actionable
error rather than serving an empty lesson.

If none of these identify a page — or a title is genuinely ambiguous —
a clear error is raised instead of silently serving the wrong lesson's
content.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.core.exceptions import CourseNotFound, LessonNotFound, MoodleIntegrationError
from app.db.repositories.courses import CourseRepository
from app.db.repositories.lessons import LessonRepository
from app.models.lesson import Lesson
from app.services.course_content.render import render_lesson_html
from app.services.moodle.client import MoodleClient
from app.services.moodle.lessons import compute_lesson_page_names
from app.services.moodle.mapper import extract_lesson_id, strip_lesson_id_marker
from app.services.moodle.page_content import apply_page_bodies, load_page_bodies

#: Moodle activity type for the published lesson pages created by the
#: local ai_course_engine plugin (``local_ai_course_engine_add_page``).
PAGE_MODNAME = "page"


@dataclass
class MoodleModule:
    """A single module (activity/resource) inside a Moodle course section."""

    cmid: int
    name: str
    modname: str
    content: str | None = None
    content_format: int | None = None
    url: str | None = None
    lesson_id: uuid.UUID | None = None


@dataclass
class MoodleSection:
    """One course section (week) in the published Moodle course."""

    section_number: int
    name: str
    summary: str | None = None
    modules: list[MoodleModule] = field(default_factory=list)


@dataclass
class MoodleCourseStructure:
    """The full published structure of one Moodle course."""

    course_id: uuid.UUID
    moodle_course_id: int
    title: str
    fullname: str
    shortname: str
    moodle_url: str | None = None
    sections: list[MoodleSection] = field(default_factory=list)


@dataclass
class MoodleLessonContent:
    """The published HTML content of one lesson (Moodle Page activity)."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    content_html: str
    content_format: int | None = None
    page_name: str | None = None


def _module_content(module: dict) -> str | None:
    """Return the page/label body HTML from a module's contents, if any."""
    contents = module.get("contents") or []
    if not isinstance(contents, list) or not contents:
        return None
    first = contents[0]
    if not isinstance(first, dict):
        return None
    content = first.get("content")
    return content if isinstance(content, str) else None


def _module_content_format(module: dict) -> int | None:
    """Return the content format declared for a module's contents, if any."""
    contents = module.get("contents") or []
    if not isinstance(contents, list) or not contents:
        return None
    first = contents[0]
    if not isinstance(first, dict):
        return None
    content_format = first.get("contentformat")
    return content_format if isinstance(content_format, int) else None


def _page_modules(raw_sections: list[dict]) -> list[MoodleModule]:
    """Return every page module in a course, in section order."""
    modules: list[MoodleModule] = []
    for section in raw_sections or []:
        for module in section.get("modules") or []:
            if (
                isinstance(module, dict)
                and module.get("modname") == PAGE_MODNAME
            ):
                modules.append(MoodleCourseContentService._map_module(module))
    return modules


class MoodleCourseContentService:
    """Retrieve published Moodle course structure and lesson content."""

    def __init__(
        self,
        client: MoodleClient,
        course_repository: CourseRepository,
        lesson_repository: LessonRepository,
    ) -> None:
        self._client = client
        self._course_repository = course_repository
        self._lesson_repository = lesson_repository

    # ------------------------------------------------------------------
    # Course structure
    # ------------------------------------------------------------------

    async def get_course_structure(
        self, course_id: uuid.UUID
    ) -> MoodleCourseStructure:
        """Return the published Moodle structure for an internal course.

        The internal course record preserves the link to its Moodle course
        id (``moodle_course_id``). The published sections, their order, and
        the page modules inside each section are read from Moodle with a
        single ``core_course_get_contents`` call.
        """
        course = await self._course_repository.get_by_id(course_id)
        if course is None:
            raise CourseNotFound(f"Course {course_id} was not found.")
        if course.moodle_course_id is None:
            raise MoodleIntegrationError(
                "Course has no Moodle course id; it has not been published to Moodle.",
                details={"course_id": str(course_id)},
            )

        raw_sections = await self._client.get_course_contents(course.moodle_course_id)
        sections = [self._map_section(section) for section in raw_sections or []]
        sections.sort(key=lambda section: section.section_number)

        lessons = await self._lesson_repository.list_publishable_by_curriculum(
            course.curriculum_id
        )
        self._assign_lesson_ids(sections, lessons)

        return MoodleCourseStructure(
            course_id=course.id,
            moodle_course_id=course.moodle_course_id,
            moodle_url=course.moodle_url,
            title=course.title,
            fullname=course.fullname,
            shortname=course.shortname,
            sections=sections,
        )

    @staticmethod
    def _assign_lesson_ids(
        sections: list[MoodleSection], lessons: list[Lesson]
    ) -> None:
        """
        Resolve each published Page module to the internal lesson it came
        from, so callers can open exactly that lesson without guessing
        from the (possibly disambiguated) page title.

        Resolution mirrors lesson content lookup: identity marker first,
        then the deterministic course-wide page name, then a raw title
        that is unique among the lessons.
        """
        if not lessons:
            return

        by_id = {lesson.id: lesson for lesson in lessons}
        name_to_id: dict[str, uuid.UUID] = {}
        for lesson_id, name in compute_lesson_page_names(lessons).items():
            name_to_id.setdefault(name, lesson_id)

        ids_by_title: dict[str, list[uuid.UUID]] = {}
        for lesson in lessons:
            ids_by_title.setdefault(lesson.title, []).append(lesson.id)
        unique_title_to_id = {
            title: ids[0] for title, ids in ids_by_title.items() if len(ids) == 1
        }

        for section in sections:
            for module in section.modules:
                if module.modname != PAGE_MODNAME:
                    continue
                marker = extract_lesson_id(module.content)
                if marker in by_id:
                    module.lesson_id = marker
                    continue
                lesson_id = name_to_id.get(module.name)
                if lesson_id is not None:
                    module.lesson_id = lesson_id
                    continue
                module.lesson_id = unique_title_to_id.get(module.name)

    # ------------------------------------------------------------------
    # Single lesson content
    # ------------------------------------------------------------------

    async def get_lesson_content(
        self, course_id: uuid.UUID, lesson_id: uuid.UUID
    ) -> MoodleLessonContent:
        """
        Return the published Moodle page content for one lesson.

        The lesson must belong to the course's curriculum. Its content is
        the HTML body of the Moodle Page activity it was published as,
        resolved through the lesson's identity marker, its deterministic
        published page name, or (for legacy courses) its unique title. If
        the lesson cannot be resolved to exactly one page, a clear error
        is raised instead of fabricating or guessing content.
        """
        course = await self._course_repository.get_by_id(course_id)
        if course is None:
            raise CourseNotFound(f"Course {course_id} was not found.")
        if course.moodle_course_id is None:
            raise MoodleIntegrationError(
                "Course has no Moodle course id; it has not been published to Moodle.",
                details={"course_id": str(course_id)},
            )

        lesson = await self._lesson_repository.get_by_id(lesson_id)
        if lesson is None or lesson.curriculum_id != course.curriculum_id:
            raise LessonNotFound(f"Lesson {lesson_id} was not found in this course.")

        raw_sections = await self._client.get_course_contents(course.moodle_course_id)
        apply_page_bodies(
            raw_sections or [],
            await load_page_bodies(self._client, course.moodle_course_id),
        )
        pages = _page_modules(raw_sections or [])

        # 1. The page this very lesson was published from.
        for page in pages:
            if extract_lesson_id(page.content) == lesson.id:
                return self._lesson_content(course, lesson, page)

        # 2. The lesson's deterministic, course-wide unique page name.
        publishable = await self._lesson_repository.list_publishable_by_curriculum(
            lesson.curriculum_id
        )
        expected_name = compute_lesson_page_names(publishable).get(lesson.id)
        if expected_name is not None:
            name_matches = [page for page in pages if page.name == expected_name]
            if len(name_matches) == 1:
                return self._lesson_content(course, lesson, name_matches[0])

        # 3./4. Legacy courses published before markers and disambiguated
        # names existed: resolve by title, and only accept a shared title
        # when exactly one of the pages carries this lesson's content.
        title_matches = [page for page in pages if page.name == lesson.title]
        if len(title_matches) == 1:
            return self._lesson_content(course, lesson, title_matches[0])
        if len(title_matches) > 1:
            rendered = render_lesson_html(lesson)
            content_matches = [
                page
                for page in title_matches
                if strip_lesson_id_marker(page.content or "") == rendered
            ]
            if len(content_matches) == 1:
                return self._lesson_content(course, lesson, content_matches[0])
            raise LessonNotFound(
                "This lesson's title is shared by "
                f"{len(title_matches)} published pages that cannot be told "
                "apart. Re-publish the course so every lesson page carries "
                "its own identity, or remove the duplicate pages in Moodle.",
                details={
                    "lesson_id": str(lesson_id),
                    "lesson_title": lesson.title,
                    "moodle_course_id": course.moodle_course_id,
                    "matching_page_cmids": [page.cmid for page in title_matches],
                },
            )

        raise LessonNotFound(
            "This lesson has not been published as a Moodle Page activity, "
            "so its content is not available from Moodle. Re-publish the "
            "course to make its content available.",
            details={
                "lesson_id": str(lesson_id),
                "lesson_title": lesson.title,
                "moodle_course_id": course.moodle_course_id,
            },
        )

    @staticmethod
    def _lesson_content(
        course, lesson, page: MoodleModule
    ) -> MoodleLessonContent:
        """
        Build the learner-facing content read for a resolved page.

        A published lesson page always has a body. If Moodle resolves the
        page but returns no body, that is a Moodle/configuration problem,
        not an empty lesson: surface it clearly instead of silently
        rendering a blank lesson and recording success.
        """
        if page.content is None:
            raise MoodleIntegrationError(
                "Moodle resolved this lesson's published page but did not "
                "return its body. Add mod_page_get_pages_by_courses to the "
                "token's external service (capability mod/page:view) and "
                "retry, or re-publish the course.",
                details={
                    "lesson_id": str(lesson.id),
                    "lesson_title": lesson.title,
                    "page_cmid": page.cmid,
                    "page_name": page.name,
                },
            )
        return MoodleLessonContent(
            course_id=course.id,
            lesson_id=lesson.id,
            title=lesson.title,
            content_html=strip_lesson_id_marker(page.content),
            content_format=page.content_format,
            page_name=page.name,
        )

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _map_module(module: dict) -> MoodleModule:
        return MoodleModule(
            cmid=int(module.get("id", 0)),
            name=module.get("name") or "",
            modname=module.get("modname") or "",
            content=_module_content(module),
            content_format=_module_content_format(module),
            url=module.get("url"),
        )

    @staticmethod
    def _map_section(raw: dict) -> MoodleSection:
        modules = [
            MoodleCourseContentService._map_module(module)
            for module in (raw.get("modules") or [])
            if isinstance(module, dict)
        ]
        return MoodleSection(
            section_number=int(raw.get("section", 0)),
            name=raw.get("name") or f"Section {raw.get('section', '?')}",
            summary=raw.get("summary"),
            modules=modules,
        )
