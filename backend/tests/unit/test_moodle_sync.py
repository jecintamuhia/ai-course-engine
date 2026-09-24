"""Unit tests for MoodleSyncService (mocked dependencies, no I/O)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.core.exceptions import (
    CurriculumNotFound,
    CurriculumValidationError,
    MoodleIntegrationError,
    MoodlePublishBlockedError,
)
from app.models.course import CourseStatus
from app.models.curriculum import Curriculum, CurriculumStatus
from app.services.moodle.preflight import FUNCTION_REQUIREMENTS
from app.services.moodle.sync import MoodleSyncService

ALL_FUNCTIONS = list(FUNCTION_REQUIREMENTS)


def _site_info(*, functions: list[str] | None = None) -> dict:
    """A site-info payload exposing the given web service functions."""
    return {
        "sitename": "Test Moodle",
        "siteurl": "https://moodle.example.com",
        "release": "4.5.1",
        "username": "ws-user",
        "functions": [
        {"name": name, "version": 0} for name in functions or ALL_FUNCTIONS
    ],
    }


def _verified_contents(week_count: int) -> list[dict]:
    """Course contents that satisfy the post-publish verification."""
    return [
        {
            "id": week_number,
            "section": week_number,
            "name": f"Week {week_number}",
            "modules": [{"modname": "page", "name": f"Week {week_number}"}],
        }
        for week_number in range(1, week_count + 1)
    ]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_curriculum(
    *,
    id_: uuid.UUID | None = None,
    status: CurriculumStatus = CurriculumStatus.APPROVED,
    title: str = "ML Course",
    week_count: int = 2,
) -> MagicMock:
    """Return a mock Curriculum loaded by CurriculumRepository."""
    c = MagicMock(spec=Curriculum)
    c.id = id_ or uuid.uuid4()
    c.status = status
    c.title = title
    units = []
    for i in range(1, week_count + 1):
        u = MagicMock()
        u.week_number = i
        u.title = f"Week {i}"
        u.description = f"Week {i} description"
        u.learning_objectives = [f"Objective {i}"]
        link = MagicMock()
        link.topic = MagicMock(title=f"Topic {i}")
        link.order_index = 0
        u.topic_links = [link]
        units.append(u)
    c.units = units
    return c


def _make_service(client_handler=None, curriculum=None):
    """Build a sync service with mocked repos and injectable client responses."""
    client = AsyncMock()
    repo = AsyncMock()
    course_repo = AsyncMock()

    curriculum_obj = curriculum or _make_curriculum()
    repo.get_by_id.return_value = curriculum_obj
    repo.list_latest_by_document.return_value = []

    # Preflight defaults: every required function is exposed and the
    # configured category exists, so the readiness gate passes.
    client.get_site_info.return_value = _site_info()
    client.get_categories.return_value = [{"id": 1, "name": "Default"}]

    return (
        MoodleSyncService(
            client,
            repo,
            course_repo,
            moodle_base_url="https://moodle.example.com",
            moodle_course_category_id=1,
        ),
        client,
        repo,
        course_repo,
        curriculum_obj,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckConnection:
    @pytest.mark.anyio
    async def test_returns_site_info(self):
        s, client, *_ = _make_service()
        client.get_site_info.return_value = {
            "sitename": "Test Moodle",
            "siteurl": "https://moodle.example.com",
            "version": "4.4",
            "username": "admin",
        }
        result = await s.check_connection()
        assert result["connected"] is True
        assert result["site_name"] == "Test Moodle"
        client.get_site_info.assert_awaited_once()


class TestPublishCurriculum:
    @pytest.mark.anyio
    async def test_raises_when_not_approved(self):
        c = _make_curriculum(status=CurriculumStatus.DRAFT)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        with pytest.raises(CurriculumValidationError):
            await s.publish_curriculum(c.id)

    @pytest.mark.anyio
    async def test_raises_when_not_found(self):
        s, client, repo, course_repo, _ = _make_service()
        repo.get_by_id.return_value = None
        with pytest.raises(CurriculumNotFound):
            await s.publish_curriculum(uuid.uuid4())

    @pytest.mark.anyio
    async def test_creates_new_moodle_course(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 42, "shortname": "cs"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(c.id)

        assert result.moodle_course_id == 42
        assert result.created is True
        client.create_course.assert_awaited_once()
        assert c.status == CurriculumStatus.PUBLISHED

    @pytest.mark.anyio
    async def test_reuses_existing_moodle_course(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        client.find_course_by_idnumber.return_value = {"id": 10}
        client.update_course.return_value = None
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(c.id)

        assert result.created is False
        client.update_course.assert_awaited_once_with(
            10,
            fullname=client.update_course.call_args.kwargs["fullname"],
            shortname=client.update_course.call_args.kwargs["shortname"],
            summary=client.update_course.call_args.kwargs["summary"],
        )

    @pytest.mark.anyio
    async def test_adds_page_module_per_section(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        client.find_course_by_idnumber.return_value = {"id": 10}
        # No sections/pages on the first read; pages exist after the sync.
        client.get_course_contents.side_effect = [
            [],
            _verified_contents(2),
        ]
        course_repo.get_by_curriculum.return_value = None

        await s.publish_curriculum(c.id)

        assert client.add_page_module.await_count == 2
        assert client.update_section.await_count == 2

    @pytest.mark.anyio
    async def test_updates_sections_by_number_instead_of_creating(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        client.find_course_by_idnumber.return_value = {"id": 10}
        # First read (sync): sections exist but have no page resources.
        # Second read (post-publish verification): pages now present.
        client.get_course_contents.side_effect = [
            [
                {"id": 1, "section": 1, "name": "Week 1", "modules": []},
                {"id": 2, "section": 2, "name": "Week 2", "modules": []},
            ],
            _verified_contents(2),
        ]
        course_repo.get_by_curriculum.return_value = None

        await s.publish_curriculum(c.id)

        assert client.update_section.await_count == 2
        assert client.add_page_module.await_count == 2
        for call in client.update_section.call_args_list:
            assert call.kwargs["section_number"] in (1, 2)

    @pytest.mark.anyio
    async def test_republish_does_not_duplicate_page_modules(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        client.find_course_by_idnumber.return_value = {"id": 10}
        client.get_course_contents.return_value = [
            {
                "id": 1,
                "section": 1,
                "name": "Week 1",
                "modules": [{"modname": "page", "name": "Week 1"}],
            },
            {
                "id": 2,
                "section": 2,
                "name": "Week 2",
                "modules": [{"modname": "page", "name": "Week 2"}],
            },
        ]
        course_repo.get_by_curriculum.return_value = None

        await s.publish_curriculum(c.id)

        assert client.update_section.await_count == 2
        assert client.add_page_module.await_count == 0


class TestVerifyCourse:
    @pytest.mark.anyio
    async def test_returns_course_contents(self):
        s, client, repo, course_repo, _ = _make_service()

        course_id = uuid.uuid4()
        mock_course = MagicMock()
        mock_course.moodle_course_id = 42
        mock_course.moodle_url = "https://moodle.example.com/course/view.php?id=42"
        course_repo.get_by_id.return_value = mock_course

        client.get_course_contents.return_value = [
            {"id": 1, "name": "Section 1", "section": 1, "modules": [{"id": 10}]},
            {
                "id": 2,
                "name": "Section 2",
                "section": 2,
                "modules": [{"id": 11}, {"id": 12}],
            },
        ]

        result = await s.verify_course(course_id)

        assert result["found"] is True
        assert result["sections_found"] == 2
        assert result["modules_found"] == 3
        assert len(result["section_names"]) == 2


class TestCategoryValidation:
    @pytest.mark.anyio
    async def test_category_override_is_used_for_creation(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = [
            {"id": 7, "name": "Custom Category"}
        ]
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 55, "shortname": "cs"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(c.id, category_id_override=7)

        assert client.get_categories.await_args.kwargs == {"category_id": 7}
        assert client.create_course.call_args.kwargs["category_id"] == 7
        assert result.moodle_course_id == 55

    @pytest.mark.anyio
    async def test_default_category_falls_back_to_configured(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = [{"id": 1, "name": "Default"}]
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 60, "shortname": "cs"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        await s.publish_curriculum(c.id)

        assert client.get_categories.await_args.kwargs == {"category_id": 1}
        assert client.create_course.call_args.kwargs["category_id"] == 1

    @pytest.mark.anyio
    async def test_raises_when_category_not_found(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = []

        with pytest.raises(MoodleIntegrationError, match="category"):
            await s.publish_curriculum(c.id)

        client.find_course_by_idnumber.assert_not_awaited()


class TestPublishOverrides:
    @pytest.mark.anyio
    async def test_fullname_and_shortname_overrides_flow_to_create(self):
        c = _make_curriculum(
            status=CurriculumStatus.APPROVED, title="Default Title"
        )
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = [{"id": 1, "name": "Cat"}]
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 10, "shortname": "x"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(
            c.id,
            fullname_override="My Full Name",
            shortname_override="my-short",
        )

        kwargs = client.create_course.call_args.kwargs
        assert kwargs["fullname"] == "My Full Name"
        assert kwargs["shortname"] == "my-short"
        assert result.course_fullname == "My Full Name"
        assert result.course_shortname == "my-short"

    @pytest.mark.anyio
    async def test_idnumber_override_is_used_for_find_or_create(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = [{"id": 1, "name": "Cat"}]
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 11, "shortname": "x"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        await s.publish_curriculum(c.id, idnumber_override="manual-id")

        assert client.find_course_by_idnumber.await_args.args[0] == "manual-id"
        assert client.create_course.call_args.kwargs["idnumber"] == "manual-id"

    @pytest.mark.anyio
    async def test_empty_shortname_falls_back_to_mapper_default(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, title="Course X")
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = [{"id": 1, "name": "Cat"}]
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 12, "shortname": "x"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(
            c.id, fullname_override="  ", shortname_override="  "
        )

        assert client.create_course.call_args.kwargs["fullname"] != "  "
        assert result.course_fullname != "  "


class TestPublishPreflightGate:
    @pytest.mark.anyio
    async def test_publish_blocked_when_capability_missing(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_site_info.return_value = _site_info(
            functions=[
                name
                for name in ALL_FUNCTIONS
                if name != "core_course_create_courses"
            ]
        )

        with pytest.raises(MoodlePublishBlockedError) as exc_info:
            await s.publish_curriculum(c.id)

        assert exc_info.value.status_code == 409
        issues = exc_info.value.details["issues"]
        assert issues[0]["kind"] == "missing_capability"
        assert issues[0]["ws_function"] == "core_course_create_courses"
        assert issues[0]["capability"] == "moodle/course:create"
        assert "core_course_create_courses" in exc_info.value.details[
            "ws_functions_required"
        ]
        client.find_course_by_idnumber.assert_not_awaited()
        client.create_course.assert_not_awaited()
        assert c.status == CurriculumStatus.APPROVED

    @pytest.mark.anyio
    async def test_publish_blocked_when_category_invalid(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.get_categories.return_value = []

        with pytest.raises(MoodleIntegrationError, match="category"):
            await s.publish_curriculum(c.id)

        client.find_course_by_idnumber.assert_not_awaited()
        assert c.status == CurriculumStatus.APPROVED


class TestPublishVerificationGate:
    @pytest.mark.anyio
    async def test_unverified_publish_is_never_reported_successful(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 42, "shortname": "cs"}
        client.get_course_contents.return_value = []
        course_repo.get_by_curriculum.return_value = None

        with pytest.raises(MoodleIntegrationError, match="could not be verified"):
            await s.publish_curriculum(c.id)

        assert c.status == CurriculumStatus.APPROVED
        course_repo.add.assert_awaited_once()
        partial = course_repo.add.await_args.args[0]
        assert partial.status == CourseStatus.SYNC_FAILED
        assert partial.moodle_course_id == 42
        assert partial.sync_error
        assert "cannot be reported as successful" in partial.sync_error

    @pytest.mark.anyio
    async def test_publish_records_synced_when_verified(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)
        client.find_course_by_idnumber.return_value = None
        client.create_course.return_value = {"id": 42, "shortname": "cs"}
        client.get_course_contents.return_value = _verified_contents(2)
        course_repo.get_by_curriculum.return_value = None

        result = await s.publish_curriculum(c.id)

        course_repo.add.assert_awaited_once()
        record = course_repo.add.await_args.args[0]
        assert record.status == CourseStatus.SYNCED
        assert record.sync_error is None
        assert result.verified is True
        assert c.status == CurriculumStatus.PUBLISHED


class TestPublishResumableRetry:
    @pytest.mark.anyio
    async def test_retry_resumes_partial_publish_without_duplicates(self):
        c = _make_curriculum(status=CurriculumStatus.APPROVED, week_count=2)
        s, client, repo, course_repo, _ = _make_service(curriculum=c)

        # First attempt finds no Moodle course, creates it, syncs sections
        # and pages, but the post-publish verification reads no contents.
        client.find_course_by_idnumber.side_effect = [None, {"id": 42}]
        client.create_course.return_value = {"id": 42, "shortname": "cs"}
        client.get_course_contents.return_value = []
        course_repo.get_by_curriculum.return_value = None

        with pytest.raises(MoodleIntegrationError, match="could not be verified"):
            await s.publish_curriculum(c.id)
        assert c.status == CurriculumStatus.APPROVED
        assert client.add_page_module.await_count == 2

        # The partial state is persisted; the second publish reuses the
        # same Moodle course and only adds what is still missing.
        partial = course_repo.add.await_args.args[0]
        course_repo.get_by_curriculum.return_value = partial
        client.get_course_contents.return_value = _verified_contents(2)

        result = await s.publish_curriculum(c.id)

        assert result.verified is True
        assert result.created is False
        assert client.create_course.await_count == 1
        assert client.add_page_module.await_count == 2
        assert client.update_section.await_count == 4
        assert partial.status == CourseStatus.SYNCED
        assert partial.sync_error is None
        assert c.status == CurriculumStatus.PUBLISHED
