"""Unit tests for the Moodle REST client (httpx.MockTransport)."""

import json
from urllib.parse import parse_qs

import httpx
import pytest
from app.core.exceptions import MoodleIntegrationError
from app.services.moodle.client import MoodleClient

# ---------------------------------------------------------------------------
# Mock transport factory
# ---------------------------------------------------------------------------


def _transport(handler):
    """Build an httpx.MockTransport from a callable handler(request) -> Response."""
    return httpx.MockTransport(handler)


def _json_response(data, status=200):
    return httpx.Response(
        status_code=status,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
    )


def _error_response(status=403, message="Forbidden"):
    return httpx.Response(
        status_code=status,
        content=json.dumps({"error": message}).encode(),
    )


def _make_client(handler):
    transport = _transport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return MoodleClient(
        "https://moodle.example.com",
        "fake-token-123",
        http_client=http_client,
    )


def _form(body: bytes) -> dict[str, str]:
    """Decode the x-www-form-urlencoded POST body into a flat dict."""
    parsed = parse_qs(body.decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


# ---------------------------------------------------------------------------
# _call / error handling
# ---------------------------------------------------------------------------


class TestMoodleClientCall:
    @pytest.mark.anyio
    async def test_returns_json_data(self):
        def handler(request):
            return _json_response({"sitename": "Test Site", "username": "admin"})

        client = _make_client(handler)
        result = await client.get_site_info()
        assert result["sitename"] == "Test Site"

    @pytest.mark.anyio
    async def test_raises_on_app_error(self):
        def handler(request):
            return _json_response(
                {
                    "exception": "dml_exception",
                    "errorcode": "invalidtoken",
                    "message": "Token is invalid.",
                },
            )

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError) as exc_info:
            await client.get_site_info()
        assert "Token is invalid" in str(exc_info.value)
        assert exc_info.value.details["errorcode"] == "invalidtoken"

    @pytest.mark.anyio
    async def test_raises_on_403(self):
        def handler(request):
            return _error_response(403, "Forbidden")

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError) as exc_info:
            await client.get_site_info()
        assert "HTTP 403" in str(exc_info.value)

    @pytest.mark.anyio
    async def test_raises_on_server_error(self):
        def handler(request):
            return _error_response(500, "Server error")

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError):
            await client.get_site_info()

    @pytest.mark.anyio
    async def test_raises_on_invalid_json(self):
        def handler(request):
            return httpx.Response(200, content=b"not-json")

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError, match="non-JSON"):
            await client.get_site_info()

    @pytest.mark.anyio
    async def test_raises_on_transport_error(self):
        def handler(request):
            raise httpx.ConnectError("Connection refused")

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError, match="Could not reach Moodle"):
            await client.get_site_info()

    @pytest.mark.anyio
    async def test_raises_on_timeout(self):
        def handler(request):
            raise httpx.TimeoutException("Timed out reading from Moodle")

        client = _make_client(handler)
        with pytest.raises(
            MoodleIntegrationError, match="Could not reach Moodle"
        ) as exc_info:
            await client.get_site_info()
        assert exc_info.value.details["function"] == "core_webservice_get_site_info"

    @pytest.mark.anyio
    async def test_sends_correct_function_name(self):
        sent_function = {}

        def handler(request):
            body = request.content.decode()
            # Extract wsfunction from POST body
            for part in body.split("&"):
                if part.startswith("wsfunction="):
                    sent_function["name"] = part.split("=", 1)[1]
            return _json_response({"ok": True})

        client = _make_client(handler)
        await client._call("core_webservice_get_site_info")
        assert sent_function["name"] == "core_webservice_get_site_info"


# ---------------------------------------------------------------------------
# find_course_by_idnumber
# ---------------------------------------------------------------------------


class TestFindCourseByIdnumber:
    @pytest.mark.anyio
    async def test_returns_first_match(self):
        def handler(request):
            return _json_response({"courses": [{"id": 1, "shortname": "test"}]})

        client = _make_client(handler)
        result = await client.find_course_by_idnumber("MY-COURSE")
        assert result["id"] == 1

    @pytest.mark.anyio
    async def test_returns_none_when_empty(self):
        def handler(request):
            return _json_response({"courses": []})

        client = _make_client(handler)
        result = await client.find_course_by_idnumber("MISSING")
        assert result is None


# ---------------------------------------------------------------------------
# create_course
# ---------------------------------------------------------------------------


class TestCreateCourse:
    @pytest.mark.anyio
    async def test_returns_created_course(self):
        def handler(request):
            return _json_response([{"id": 42, "shortname": "new-course"}])

        client = _make_client(handler)
        result = await client.create_course(
            fullname="New Course",
            shortname="new-course",
            idnumber="ai-ece-1",
            category_id=1,
            summary="<p>Overview</p>",
            num_sections=4,
        )
        assert result["id"] == 42

    @pytest.mark.anyio
    async def test_raises_on_empty_response(self):
        def handler(request):
            return _json_response([])

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError, match="no course object"):
            await client.create_course(
                fullname="C",
                shortname="c",
                idnumber="x",
                category_id=1,
                summary="s",
                num_sections=1,
            )


# ---------------------------------------------------------------------------
# create_section / update_section
# ---------------------------------------------------------------------------


class TestSections:
    @pytest.mark.anyio
    async def test_creates_section_with_expected_params(self):
        sent = {}

        def handler(request):
            sent.update(_form(request.content))
            return _json_response({"id": 9})

        client = _make_client(handler)
        result = await client.create_section(
            42,
            section_number=3,
            name="Week 3",
            summary="<p>Summary</p>",
        )

        assert result["id"] == 9
        assert sent["wsfunction"] == "core_course_create_sections"
        assert sent["sections[0][section]"] == "3"
        assert sent["sections[0][name]"] == "Week 3"
        assert sent["sections[0][summary]"] == "<p>Summary</p>"

    @pytest.mark.anyio
    async def test_updates_section_with_id_and_params(self):
        sent = {}

        def handler(request):
            sent.update(_form(request.content))
            return _json_response({"id": 9})

        client = _make_client(handler)
        result = await client.update_section(
            42,
            9,
            name="Week 3 (updated)",
            summary="<p>New text</p>",
        )

        assert result["id"] == 9
        assert sent["wsfunction"] == "core_course_update_sections"
        assert sent["sections[0][id]"] == "9"
        assert sent["sections[0][name]"] == "Week 3 (updated)"
        assert sent["sections[0][summary]"] == "<p>New text</p>"


# ---------------------------------------------------------------------------
# get_categories
# ---------------------------------------------------------------------------


class TestGetCategories:
    @pytest.mark.anyio
    async def test_returns_list_of_categories(self):
        def handler(request):
            return _json_response(
                [{"id": 1, "name": "Category A"}, {"id": 2, "name": "Category B"}]
            )

        client = _make_client(handler)
        result = await client.get_categories()
        assert result == [
            {"id": 1, "name": "Category A"},
            {"id": 2, "name": "Category B"},
        ]

    @pytest.mark.anyio
    async def test_passes_single_category_criterion_when_requested(self):
        sent = {}

        def handler(request):
            sent.update(_form(request.content))
            return _json_response([{"id": 7, "name": "Category Seven"}])

        client = _make_client(handler)
        result = await client.get_categories(category_id=7)

        assert sent["wsfunction"] == "core_course_get_categories"
        assert sent["criteria[0][key]"] == "id"
        assert sent["criteria[0][value]"] == "7"
        assert result[0]["id"] == 7

    @pytest.mark.anyio
    async def test_returns_empty_list_for_non_list_json_response(self):
        def handler(request):
            return _json_response({"categories": [], "some_key": "value"})

        client = _make_client(handler)
        result = await client.get_categories()
        assert result == []

    @pytest.mark.anyio
    async def test_raises_moodle_error_when_exception_present(self):
        def handler(request):
            return _json_response(
                {"exception": "dml_exception", "errorcode": "invalidtoken"}
            )

        client = _make_client(handler)
        with pytest.raises(MoodleIntegrationError):
            await client.get_categories()

    @pytest.mark.anyio
    async def test_returns_empty_list_when_no_category_matches(self):
        def handler(request):
            return _json_response([])

        client = _make_client(handler)
        result = await client.get_categories(category_id=999)
        assert result == []
