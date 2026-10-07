"""Route-level tests for the Moodle status endpoint.

Exercises /api/v1/moodle/status without a live Moodle: the client on
``app.state`` is injected directly (no DB/lifespan side effects).
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock
from urllib.parse import parse_qs

import httpx
import pytest
from app.api.v1.curriculum import get_curriculum_service
from app.core.exceptions import MoodleIntegrationError
from app.main import app
from app.services.moodle.client import MoodleClient
from app.services.moodle.preflight import FUNCTION_REQUIREMENTS
from tests.helpers import install_auth_override

STATUS_URL = "/api/v1/moodle/status"
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
