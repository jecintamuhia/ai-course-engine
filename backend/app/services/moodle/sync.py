"""Moodle publishing service: curriculum → Moodle course synchronization.

The sync flow is idempotent. Publishing the same curriculum twice:

1. always reuses the existing Moodle course found by ``idnumber``
   (``ai-ece-<curriculum_id>``);
2. updates weekly section names/summaries in place;
3. adds a "Page" activity per lecturer-approved lesson (when a lesson
   renderer is provided) only if a page with the lesson's name does not
   already exist in that week's section. Lessons with byte-identical
   content are published once, so duplicated curriculum/lesson items do
   not create duplicate pages. No page is ever created that repeats a
   weekly section's name: the section itself represents the week.

Only APPROVED (or already PUBLISHED) curricula can be published; the
status transition to PUBLISHED is recorded on success. Moodle call
failures are surfaced to the caller and, for previously published
courses, recorded on the persisted Course row.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.exceptions import (
    CourseNotFound,
    CurriculumNotFound,
    CurriculumValidationError,
    MoodleIntegrationError,
    MoodlePublishBlockedError,
)
from app.core.logging import get_logger
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.models.course import Course, CourseStatus
from app.models.curriculum import Curriculum, CurriculumStatus
from app.models.curriculum_unit import CurriculumUnit
from app.services.moodle.client import MoodleClient
from app.services.moodle.mapper import (
    MoodleCoursePlan,
    MoodleLessonPlan,
    build_course_plan,
)
from app.services.moodle.preflight import issue_to_dict, run_readiness_check

logger = get_logger(__name__)

_MAX_SYNC_ERROR_LENGTH = 2000


def _truncate(value: str, max_length: int) -> str:
    """Truncate an error message to fit the persisted Text column."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


@dataclass
class MoodlePublishResult:
    """Outcome of publishing a curriculum to Moodle."""

    course_id: uuid.UUID
    moodle_course_id: int
    course_fullname: str
    course_shortname: str
    course_url: str
    idnumber: str
    created: bool
    sections_published: int
    resources_published: int
    verified: bool


class MoodleSyncService:
    """Coordinates idempotent publishing of curricula to Moodle."""

    def __init__(
        self,
        client: MoodleClient,
        curriculum_repository: CurriculumRepository,
        course_repository: CourseRepository,
        *,
        moodle_base_url: str | None = None,
        moodle_course_category_id: int = 1,
    ) -> None:
        self._client = client
        self._curriculum_repository = curriculum_repository
        self._course_repository = course_repository
        self._moodle_base_url = (moodle_base_url or "").rstrip("/")
        self._category_id = moodle_course_category_id

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def check_connection(self) -> dict:
        """Return site info for the configured Moodle connection."""
        info = await self._client.get_site_info()
        return {
            "connected": True,
            "site_name": info.get("sitename"),
            "site_url": info.get("siteurl"),
            "api_version": info.get("version"),
            "username": info.get("username"),
        }

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_curriculum(
        self,
        curriculum_id: uuid.UUID,
        *,
        idnumber_override: str | None = None,
        fullname_override: str | None = None,
        shortname_override: str | None = None,
        category_id_override: int | None = None,
        lesson_renderer: (
            Callable[[CurriculumUnit], list[MoodleLessonPlan]] | None
        ) = None,
    ) -> MoodlePublishResult:
        """Publish an APPROVED (or already PUBLISHED) curriculum to Moodle.

        ``lesson_renderer`` maps each weekly unit to the lecturer-approved
        lessons that should be added as page resources in that week's
        section. When omitted no lesson pages are published and the
        behaviour is identical to publishing before lessons existed.
        """
        curriculum = await self._curriculum_repository.get_by_id(curriculum_id)

        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        if curriculum.status not in (
            CurriculumStatus.APPROVED,
            CurriculumStatus.PUBLISHED,
        ):
            raise CurriculumValidationError(
                "Only APPROVED curricula can be published to Moodle.",
                details={"current_status": curriculum.status.value},
            )

        # Close the read-only transaction before any external calls.
        await self._curriculum_repository.commit()

        category_id = (
            category_id_override
            if category_id_override is not None
            else self._category_id
        )

        # Preflight gate: only read-only Moodle calls happen here. When
        # Moodle is not ready (token/capability/category problems), the
        # curriculum is left untouched and publishing never starts.
        readiness = await run_readiness_check(self._client, category_id=category_id)
        if not readiness.ready:
            issues = [issue_to_dict(issue) for issue in readiness.issues]
            summary = " ".join(
                f"{entry['kind']}: {entry['message']}" for entry in issues
            )
            raise MoodlePublishBlockedError(
                f"Moodle is not ready to publish this curriculum. {summary} "
                "No changes were made to the curriculum.",
                details={
                    "issues": issues,
                    "ws_functions_required": readiness.functions_required,
                    "capabilities_required": readiness.capabilities_required,
                },
            )

        plan = build_course_plan(
            curriculum,
            fullname_override=fullname_override,
            shortname_override=shortname_override,
            lesson_renderer=lesson_renderer,
        )
        if idnumber_override:
            plan.idnumber = idnumber_override.strip() or plan.idnumber

        existing_record = await self._course_repository.get_by_curriculum(curriculum.id)

        if existing_record is not None and existing_record.idnumber:
            # The stored idnumber is authoritative on republish: honor it
            # even if an override was supplied, so repeated publishes keep
            # reusing the same Moodle course instead of duplicating it.
            plan.idnumber = existing_record.idnumber

        moodle_course = await self._client.find_course_by_idnumber(plan.idnumber)

        created = False
        if moodle_course is None:
            moodle_course = await self._client.create_course(
                fullname=plan.fullname,
                shortname=plan.shortname,
                idnumber=plan.idnumber,
                category_id=category_id,
                summary=plan.summary_html,
                num_sections=max((w.section_number for w in plan.weeks), default=1),
            )
            created = True
        else:
            await self._client.update_course(
                int(moodle_course["id"]),
                fullname=plan.fullname,
                shortname=plan.shortname,
                summary=plan.summary_html,
            )

        moodle_course_id = int(moodle_course["id"])
        course_url = self._course_url(moodle_course_id)

        try:
            sections_published, resources_published = await self._sync_course(
                moodle_course_id=moodle_course_id,
                course_idnumber=plan.idnumber,
                plan=plan,
            )
            verified = await self._verify_sections(
                moodle_course_id=moodle_course_id, plan=plan
            )
        except MoodleIntegrationError as exc:
            await self._record_partial_failure(
                existing_record=existing_record,
                curriculum=curriculum,
                plan=plan,
                moodle_course_id=moodle_course_id,
                course_url=course_url,
                error=str(exc),
            )
            raise

        # Publishing is never reported as successful unless the live Moodle
        # contents actually match the plan. A failed verification records a
        # resumable partial state (SYNC_FAILED) and re-raises.
        if not verified:
            await self._record_partial_failure(
                existing_record=existing_record,
                curriculum=curriculum,
                plan=plan,
                moodle_course_id=moodle_course_id,
                course_url=course_url,
                error=(
                    "Moodle did not report all planned weekly sections and "
                    "page resources after publishing. Publishing cannot be "
                    "reported as successful."
                ),
            )
            raise MoodleIntegrationError(
                "Publishing could not be verified in Moodle: not all planned "
                "weekly sections and page resources were found. Re-publish to "
                "resume the sync (it is idempotent and will not duplicate "
                "existing content).",
                details={
                    "moodle_course_id": moodle_course_id,
                    "idnumber": plan.idnumber,
                    "recoverable": True,
                },
            )

        assert curriculum.status in (
            CurriculumStatus.APPROVED,
            CurriculumStatus.PUBLISHED,
        )
        curriculum.status = CurriculumStatus.PUBLISHED

        course_record = existing_record
        if course_record is None:
            course_record = Course(
                curriculum_id=curriculum.id,
                title=plan.fullname,
                fullname=plan.fullname,
                shortname=plan.shortname,
                idnumber=plan.idnumber,
                moodle_course_id=moodle_course_id,
                moodle_url=course_url,
                status=CourseStatus.SYNCED,
                sections_published=sections_published,
                resources_published=resources_published,
                last_sync_at=datetime.now(UTC),
                sync_error=None,
            )
            await self._course_repository.add(course_record)
        else:
            course_record.fullname = plan.fullname
            course_record.shortname = plan.shortname
            course_record.idnumber = plan.idnumber
            course_record.moodle_course_id = moodle_course_id
            course_record.moodle_url = course_url
            course_record.status = CourseStatus.SYNCED
            course_record.sections_published = sections_published
            course_record.resources_published = resources_published
            course_record.last_sync_at = datetime.now(UTC)
            course_record.sync_error = None

        await self._course_repository.commit()

        logger.info(
            "Published curriculum to Moodle curriculum_id=%s moodle_course_id=%s "
            "created=%s sections=%s resources=%s",
            curriculum.id,
            moodle_course_id,
            created,
            sections_published,
            resources_published,
        )

        return MoodlePublishResult(
            course_id=course_record.id,
            moodle_course_id=moodle_course_id,
            course_fullname=plan.fullname,
            course_shortname=plan.shortname,
            course_url=course_url,
            idnumber=plan.idnumber,
            created=created,
            sections_published=sections_published,
            resources_published=resources_published,
            verified=verified,
        )

    async def _verify_sections(
        self, *, moodle_course_id: int, plan: MoodleCoursePlan
    ) -> bool:
        """
        Verify the published course actually contains every planned
        section and its lesson page resources. Returns True only when the
        live Moodle contents match the plan.
        """
        contents = await self._client.get_course_contents(moodle_course_id)
        sections_by_number = {
            int(section.get("section", -1)): section for section in contents
        }

        for week in plan.weeks:
            section = sections_by_number.get(week.section_number)
            if section is None:
                return False

            modules = section.get("modules", [])

            # Mirror the sync rule: lessons with byte-identical content are
            # published once, so verification accepts a single page for the
            # first of a set of identical-content lessons.
            seen_content: set[str] = set()
            for lesson in week.lessons:
                if lesson.content_html in seen_content:
                    continue
                seen_content.add(lesson.content_html)

                has_lesson_page = any(
                    module.get("modname") == "page"
                    and module.get("name") == lesson.name
                    for module in modules
                )
                if not has_lesson_page:
                    return False

        return True

    async def verify_course(self, course_id: uuid.UUID) -> dict:
        """Verify a published course exists in Moodle and report its contents."""
        record = await self._course_repository.get_by_id(course_id)
        await self._course_repository.commit()

        if record is None:
            raise CourseNotFound(f"Course {course_id} was not found.")
        if record.moodle_course_id is None:
            raise MoodleIntegrationError(
                "Course record has no Moodle course id yet.",
            )

        contents = await self._client.get_course_contents(record.moodle_course_id)

        sections_found = len(contents)
        modules_found = sum(len(section.get("modules", [])) for section in contents)
        section_names = [
            section.get("name") or f"Section {section.get('section', '?')}"
            for section in contents
        ]

        return {
            "course_id": str(record.id),
            "moodle_course_id": record.moodle_course_id,
            "found": True,
            "sections_found": sections_found,
            "modules_found": modules_found,
            "section_names": section_names,
            "course_url": record.moodle_url,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _record_partial_failure(
        self,
        *,
        existing_record: Course | None,
        curriculum: Curriculum,
        plan: MoodleCoursePlan,
        moodle_course_id: int,
        course_url: str,
        error: str,
    ) -> None:
        """
        Persist the partially-synced course state (SYNC_FAILED) so a later
        re-publish can resume: the Moodle course id and idnumber are stored
        and the sync is idempotent (never duplicates sections/pages).
        """
        sections, resources = await self._count_existing_content(moodle_course_id)

        record = existing_record
        if record is None:
            record = Course(
                curriculum_id=curriculum.id,
                title=plan.fullname,
                fullname=plan.fullname,
                shortname=plan.shortname,
                idnumber=plan.idnumber,
                moodle_course_id=moodle_course_id,
                moodle_url=course_url,
                status=CourseStatus.SYNC_FAILED,
                sections_published=sections,
                resources_published=resources,
                last_sync_at=datetime.now(UTC),
                sync_error=_truncate(error, _MAX_SYNC_ERROR_LENGTH),
            )
            await self._course_repository.add(record)
        else:
            record.fullname = plan.fullname
            record.shortname = plan.shortname
            record.idnumber = plan.idnumber
            record.moodle_course_id = moodle_course_id
            record.moodle_url = course_url
            record.status = CourseStatus.SYNC_FAILED
            record.sections_published = sections
            record.resources_published = resources
            record.sync_error = _truncate(error, _MAX_SYNC_ERROR_LENGTH)
            record.last_sync_at = datetime.now(UTC)

        await self._course_repository.commit()

    async def _count_existing_content(self, moodle_course_id: int) -> tuple[int, int]:
        """
        Best-effort count of what already exists in the Moodle course:
        the highest week/section number and the number of 'page' modules.
        Returns (0, 0) when the contents cannot be read.
        """
        try:
            contents = await self._client.get_course_contents(moodle_course_id)
        except MoodleIntegrationError:
            return 0, 0
        sections = max(
            (int(section.get("section", 0)) for section in contents),
            default=0,
        )
        resources = sum(
            1
            for section in contents
            for module in section.get("modules", [])
            if module.get("modname") == "page"
        )
        return sections, resources

    async def _sync_course(
        self,
        *,
        moodle_course_id: int,
        course_idnumber: str,
        plan: MoodleCoursePlan,
    ) -> tuple[int, int]:
        """
        Ensure weekly sections have correct names/summaries and that every
        planned lesson page exists in its section. ``update_section``
        upserts (the plugin creates a missing section), so the weekly
        sections auto-created by ``create_courses`` are named in place.
        Lesson pages are only added when missing, so re-publishing never
        duplicates them; lessons with identical content are added once.
        Returns (sections_published, resources_published).
        """
        contents = await self._client.get_course_contents(moodle_course_id)
        modules_by_section: dict[int, list[dict]] = {}
        for section in contents:
            number = int(section.get("section", -1))
            modules_by_section.setdefault(number, []).extend(section.get("modules", []))

        sections_published = 0
        resources_published = 0

        for week in plan.weeks:
            number = week.section_number

            await self._client.update_section(
                moodle_course_id,
                section_number=number,
                name=week.section_name,
                summary=week.section_summary_html,
            )
            sections_published = max(sections_published, number)

            section_modules = modules_by_section.get(number, [])

            seen_content: set[str] = set()
            for lesson in week.lessons:
                if lesson.content_html in seen_content:
                    continue
                seen_content.add(lesson.content_html)

                existing_lesson = [
                    module
                    for module in section_modules
                    if module.get("modname") == "page"
                    and module.get("name") == lesson.name
                ]
                if not existing_lesson:
                    await self._client.add_page_module(
                        moodle_course_id,
                        section_number=number,
                        name=lesson.name,
                        content_html=lesson.content_html,
                    )
                    resources_published += 1

        return sections_published, resources_published

    def _course_url(self, moodle_course_id: int) -> str:
        """Build the Moodle web URL for a course id."""
        if not self._moodle_base_url:
            return f"course/view.php?id={moodle_course_id}"
        return f"{self._moodle_base_url}/course/view.php?id={moodle_course_id}"
