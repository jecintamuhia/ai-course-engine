"""Route-level tests for the Moodle status endpoint.

Exercises /api/v1/moodle/status without a live Moodle: the client on
``app.state`` is injected directly (no DB/lifespan side effects).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import parse_qs

import httpx
import pytest
from app.api.v1.curriculum import get_curriculum_service
from app.api.v1.moodle import get_moodle_sync_service, get_qa_service
from app.core.dependencies import get_database_session
from app.core.exceptions import (
    ConfigurationError,
    ContentQAError,
    MoodleIntegrationError,
)
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.lessons import LessonRepository
from app.main import app
from app.models.course import Course, CourseStatus
from app.models.curriculum import CurriculumStatus
from app.services.moodle.client import MoodleClient
from app.services.moodle.preflight import FUNCTION_REQUIREMENTS
from tests.helpers import install_auth_override

STATUS_URL = "/api/v1/moodle/status"
CHECK_URL = "/api/v1/moodle/check"
PREFLIGHT_URL = "/api/v1/moodle/preflight"

ALL_FUNCTIONS = list(FUNCTION_REQUIREMENTS)


@pytest.fixture(autouse=True)
def _authenticated_routes() -> None:
    """Protect every protected route with the fake authenticated user."""
    install_auth_override(app)


def _form(body: bytes) -> dict[str, str]:
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


def _json_response(data) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
    )


def _site_info(functions: list[str] | None = None) -> dict:
    return {
        "sitename": "Demo Moodle",
        "siteurl": "https://moodle.example.com",
        "release": "4.5.1",
        "version": 2024100700,
        "username": "demo-admin",
        "functions": [
            {"name": name, "version": 2024100700} for name in functions or ALL_FUNCTIONS
        ],
    }


async def _get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
    ) as client:
        return await client.get(path)


async def _post(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
    ) as client:
        return await client.post(path)


@pytest.mark.anyio
async def test_status_reports_unconfigured_without_secrets() -> None:
    app.state.moodle_client = None

    response = await _get(STATUS_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["connected"] is False
    assert "wstoken" not in response.text.lower()


@pytest.mark.anyio
async def test_status_reports_connected_without_exposing_token() -> None:
    def handler(request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=json.dumps(
                {
                    "sitename": "Demo Moodle",
                    "siteurl": "https://moodle.example.com",
                    "version": "4.5.1",
                    "username": "demo-admin",
                }
            ).encode(),
            headers={"content-type": "application/json"},
        )

    client = MoodleClient(
        "https://moodle.example.com",
        "super-secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    app.state.moodle_client = client

    response = await _get(STATUS_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["connected"] is True
    assert payload["site_name"] == "Demo Moodle"
    assert payload["username"] == "demo-admin"
    assert "super-secret-token" not in response.text


@pytest.mark.anyio
async def test_status_reports_connection_error() -> None:
    fake = AsyncMock()
    fake.get_site_info.side_effect = MoodleIntegrationError(
        "Could not reach Moodle at https://moodle.example.com.",
        details={"function": "core_webservice_get_site_info"},
    )
    app.state.moodle_client = fake

    response = await _get(STATUS_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["connected"] is False
    assert "Could not reach Moodle" in payload["error"]
    assert "wstoken" not in response.text.lower()


@pytest.mark.anyio
async def test_check_keeps_connection_when_category_probe_fails() -> None:
    fake = AsyncMock()
    fake.get_site_info.return_value = {
        "sitename": "Demo Moodle",
        "siteurl": "https://moodle.example.com",
        "version": "4.5.1",
        "username": "demo-admin",
    }
    fake.get_categories.side_effect = MoodleIntegrationError(
        "Capability moodle/course:create is missing.",
        details={"capability": "moodle/course:create"},
    )
    app.state.moodle_client = fake

    response = await _get(CHECK_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert payload["degraded"] is True
    assert "moodle/course:create" in payload["error"]
    assert payload["site_name"] == "Demo Moodle"


@pytest.mark.anyio
async def test_preflight_reports_not_configured() -> None:
    app.state.moodle_client = None

    response = await _get(PREFLIGHT_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["configured"] is False
    assert payload["issues"][0]["kind"] == "not_configured"
    assert "MOODLE_URL" in payload["issues"][0]["admin_action"]


@pytest.mark.anyio
async def test_preflight_reports_ready_when_everything_satisfied() -> None:
    def handler(request) -> httpx.Response:
        function = _form(request.content).get("wsfunction")
        if function == "core_course_get_categories":
            return _json_response([{"id": 1, "name": "Default"}])
        return _json_response(_site_info())

    client = MoodleClient(
        "https://moodle.example.com",
        "super-secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    app.state.moodle_client = client

    response = await _get(PREFLIGHT_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["configured"] is True
    assert payload["site_name"] == "Demo Moodle"
    assert payload["category_found"] is True
    assert payload["issues"] == []
    assert "super-secret-token" not in response.text


@pytest.mark.anyio
async def test_preflight_lists_missing_capability_as_admin_action() -> None:
    def handler(request) -> httpx.Response:
        function = _form(request.content).get("wsfunction")
        if function == "core_course_get_categories":
            return _json_response([{"id": 1, "name": "Default"}])
        functions = [
            name for name in ALL_FUNCTIONS if name != "core_course_create_courses"
        ]
        return _json_response(_site_info(functions))

    client = MoodleClient(
        "https://moodle.example.com",
        "super-secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    app.state.moodle_client = client

    response = await _get(PREFLIGHT_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    missing = [
        issue for issue in payload["issues"] if issue["kind"] == "missing_capability"
    ]
    assert missing
    assert missing[0]["ws_function"] == "core_course_create_courses"
    assert missing[0]["capability"] == "moodle/course:create"
    assert "capabilities_required" in payload
    assert "wstoken" not in response.text.lower()


@pytest.mark.anyio
async def test_preflight_includes_checks_and_blocking_issues() -> None:
    def handler(request) -> httpx.Response:
        function = _form(request.content).get("wsfunction")
        if function == "core_course_get_categories":
            return _json_response([{"id": 1, "name": "Default"}])
        functions = [
            name for name in ALL_FUNCTIONS if name != "core_course_create_courses"
        ]
        return _json_response(_site_info(functions))

    client = MoodleClient(
        "https://moodle.example.com",
        "super-secret-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    app.state.moodle_client = client

    response = await _get(PREFLIGHT_URL)

    payload = response.json()
    assert "checks" in payload
    assert payload["blocking_issues"] == payload["issues"]
    checks = {entry["label"]: entry for entry in payload["checks"]}
    assert checks["Moodle connection & API access"]["status"] == "ok"
    assert checks["Web service token authentication"]["status"] == "ok"
    missing_function = checks["Web service function core_course_create_courses"]
    assert missing_function["status"] == "error"
    capability = checks["Capability moodle/course:create"]
    assert capability["status"] == "error"
    assert capability["verification"] == "inferred"
    assert "cannot be queried directly" in capability["detail"]


@pytest.mark.anyio
async def test_curriculum_export_works_when_moodle_unavailable() -> None:
    """The approved curriculum stays usable (exportable) without Moodle."""
    service = AsyncMock()
    service.export_payload = AsyncMock(
        return_value={
            "format": "ai-course-engine/curriculum-export",
            "version": 1,
            "generated_at": "2026-09-17T00:00:00Z",
            "importable": False,
            "curriculum": {"id": str(uuid.uuid4()), "title": "ML Course"},
            "weeks": [],
            "source": None,
            "notes": "Reference document, not a Moodle backup.",
        }
    )
    app.dependency_overrides[get_curriculum_service] = lambda: service
    app.state.moodle_client = None

    try:
        response = await _get(f"/api/v1/curricula/{uuid.uuid4()}/export")
    finally:
        app.dependency_overrides.pop(get_curriculum_service, None)
        app.state.moodle_client = None

    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    payload = response.json()
    assert payload["format"] == "ai-course-engine/curriculum-export"
    assert payload["importable"] is False
    assert service.export_payload.await_count == 1


@pytest.mark.anyio
async def test_courses_list_exposes_publication_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Admins can read the publication state without any Moodle call."""

    now = datetime.now(UTC)
    synced = Course(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        title="WHM/cPanel/DirectAdmin/Plesk - Complete Professional Textbook",
        fullname="WHM/cPanel/DirectAdmin/Plesk - Complete Professional Textbook",
        shortname="WHM/cPanel/DirectAdmin/Plesk course",
        idnumber="ai-ece-643a805c-050d-4910-bf2d-97da7ef68dfb",
        moodle_course_id=5,
        moodle_url="https://elearning.skillupafrica.co.ke/course/view.php?id=5",
        status=CourseStatus.SYNCED,
        sections_published=16,
        resources_published=64,
        last_sync_at=now,
        sync_error=None,
        created_at=now,
        updated_at=now,
    )
    failed = Course(
        id=uuid.uuid4(),
        curriculum_id=uuid.uuid4(),
        title="Draft attempt",
        fullname="Draft attempt",
        shortname="draft",
        idnumber="ai-ece-draft",
        moodle_course_id=6,
        moodle_url="https://elearning.skillupafrica.co.ke/course/view.php?id=6",
        status=CourseStatus.SYNC_FAILED,
        sections_published=3,
        resources_published=1,
        last_sync_at=now - timedelta(days=1),
        sync_error="Moodle did not report all planned weekly sections.",
        created_at=now,
        updated_at=now,
    )

    async def fake_list_all(self) -> list[Course]:
        return [synced, failed]

    app.dependency_overrides[get_database_session] = lambda: AsyncMock()
    monkeypatch.setattr(CourseRepository, "list_all", fake_list_all)

    try:
        response = await _get("/api/v1/courses")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["courses"]) == 2

    synced_payload = next(
        c for c in payload["courses"] if c["idnumber"] == synced.idnumber
    )
    assert synced_payload["moodle_course_id"] == 5
    assert synced_payload["status"] == "synced"
    assert synced_payload["sections_published"] == 16
    assert synced_payload["sync_error"] is None
    assert synced_payload["last_sync_at"] is not None
    assert synced_payload["curriculum_id"] == str(synced.curriculum_id)

    failed_payload = next(
        c for c in payload["courses"] if c["idnumber"] == failed.idnumber
    )
    assert failed_payload["status"] == "sync_failed"
    assert "did not report" in failed_payload["sync_error"]

    # Never leak the Moodle web-service token through the courses list.
    assert "wstoken" not in response.text.lower()


class TestPublishGatePrecedence:
    """
    QA-gate error precedence on POST /api/v1/moodle/publish/{id}.

    A QA failure must be reported even when Moodle is not configured;
    only when QA passes may the Moodle configuration error surface.
    """

    def _qa_service(self, *, blocked: bool) -> AsyncMock:
        qa = AsyncMock()
        if blocked:
            qa.assert_qa_pass = AsyncMock(
                side_effect=ContentQAError(
                    "Curriculum failed content-QA; resolve the findings "
                    "before approving or publishing.",
                    details={"curriculum_id": "irrelevant", "verdict": "fail"},
                )
            )
        else:
            qa.assert_qa_pass = AsyncMock(return_value=None)
        return qa

    @pytest.mark.anyio
    async def test_qa_failure_beats_unconfigured_moodle(self) -> None:
        curriculum_id = uuid.uuid4()
        app.dependency_overrides[get_qa_service] = lambda: self._qa_service(
            blocked=True
        )
        app.dependency_overrides[get_database_session] = lambda: AsyncMock()
        app.state.moodle_client = None

        try:
            response = await _post(f"/api/v1/moodle/publish/{curriculum_id}")
        finally:
            app.dependency_overrides.pop(get_qa_service, None)
            app.dependency_overrides.pop(get_database_session, None)

        assert response.status_code == 409
        payload = response.json()
        assert payload["error"]["code"] == "qa_blocked"
        assert "content-QA" in payload["error"]["message"]

    @pytest.mark.anyio
    async def test_qa_pass_with_unconfigured_moodle_reports_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        curriculum_id = uuid.uuid4()

        async def fake_list_publishable(self, curriculum_id_):
            return []

        async def fake_get_by_id(self, curriculum_id_):
            curriculum = AsyncMock()
            curriculum.id = curriculum_id
            curriculum.status = CurriculumStatus.APPROVED
            curriculum.units = []
            curriculum.title = "Course"
            return curriculum

        app.dependency_overrides[get_qa_service] = lambda: self._qa_service(
            blocked=False
        )
        app.dependency_overrides[get_database_session] = lambda: AsyncMock()
        monkeypatch.setattr(
            LessonRepository, "list_publishable_by_curriculum", fake_list_publishable
        )
        monkeypatch.setattr(CurriculumRepository, "get_by_id", fake_get_by_id)
        app.state.moodle_client = None

        try:
            response = await _post(f"/api/v1/moodle/publish/{curriculum_id}")
        finally:
            app.dependency_overrides.pop(get_qa_service, None)
            app.dependency_overrides.pop(get_database_session, None)

        assert response.status_code == 500
        payload = response.json()
        assert payload["error"]["code"] == "configuration_error"
        assert "MOODLE_URL" in payload["error"]["message"]

    @pytest.mark.anyio
    async def test_unconfigured_moodle_does_not_block_dependency_resolution(
        self,
    ) -> None:
        """The sync service dependency builds fine without Moodle configured."""
        from app.core.config import Settings

        request = MagicMock()
        request.app.state.moodle_client = None

        service = get_moodle_sync_service(
            request=request,
            session=AsyncMock(),
            settings=Settings(),
        )

        assert service is not None

        with pytest.raises(ConfigurationError):
            await service.check_connection()
