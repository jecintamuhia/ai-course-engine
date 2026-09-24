"""Unit tests for the Moodle preflight/readiness check."""

import pytest
from app.core.exceptions import MoodleIntegrationError
from app.services.moodle.preflight import (
    FUNCTION_REQUIREMENTS,
    MoodleIssueKind,
    run_readiness_check,
)

ALL_FUNCTIONS = list(FUNCTION_REQUIREMENTS)

DEFAULT_SITE_INFO = {
    "sitename": "Test Moodle",
    "siteurl": "https://moodle.example.com",
    "release": "4.5.1",
    "version": 2024100700,
    "username": "ws-user",
    "functions": [{"name": name, "version": 2024100700} for name in ALL_FUNCTIONS],
}


class FakeClient:
    """Minimal async stand-in for MoodleClient used by preflight tests."""

    base_url = "https://moodle.example.com"

    def __init__(self, *, site_info=None, categories=None, site_info_error=None):
        self._site_info = site_info if site_info is not None else DEFAULT_SITE_INFO
        self._categories = categories if categories is not None else [{"id": 1}]
        self._site_info_error = site_info_error

    async def get_site_info(self):
        if self._site_info_error is not None:
            raise self._site_info_error
        return self._site_info

    async def get_categories(self, **kwargs):
        return self._categories


def _transport_error() -> MoodleIntegrationError:
    return MoodleIntegrationError(
        "Could not reach Moodle at https://moodle.example.com.",
        details={"function": "core_webservice_get_site_info", "reason": "timed out"},
    )


def _finding_issue(result, kind):
    return [issue for issue in result.issues if issue.kind == kind]


class TestPreflightConfiguration:
    @pytest.mark.anyio
    async def test_reports_not_configured_when_client_is_none(self):
        result = await run_readiness_check(None, category_id=1)

        assert result.ready is False
        assert result.configured is False
        assert [i.kind for i in result.issues] == [MoodleIssueKind.NOT_CONFIGURED]

    @pytest.mark.anyio
    async def test_reports_invalid_parameter_for_non_positive_category(self):
        client = FakeClient()
        result = await run_readiness_check(client, category_id=0)

        assert result.ready is False
        assert _finding_issue(result, MoodleIssueKind.INVALID_PARAMETER)
        assert result.category_found is None


class TestPreflightSuccess:
    @pytest.mark.anyio
    async def test_reports_ready_when_everything_is_satisfied(self):
        client = FakeClient()
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is True
        assert result.configured is True
        assert result.issues == []
        assert result.site_name == "Test Moodle"
        assert result.username == "ws-user"
        assert result.category_found is True
        assert set(result.functions_required) == set(ALL_FUNCTIONS)
        assert "moodle/course:create" in result.capabilities_required

    @pytest.mark.anyio
    async def test_accepts_functions_reported_as_plain_strings(self):
        info = {**DEFAULT_SITE_INFO, "functions": list(ALL_FUNCTIONS)}
        client = FakeClient(site_info=info)
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is True


class TestMissingCapability:
    @pytest.mark.anyio
    async def test_missing_course_create_reports_capability(self):
        info = {
            **DEFAULT_SITE_INFO,
            "functions": [
                name
                for name in ALL_FUNCTIONS
                if name != "core_course_create_courses"
            ],
        }
        client = FakeClient(site_info=info)
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.MISSING_CAPABILITY)
        assert len(issues) == 1
        assert issues[0].ws_function == "core_course_create_courses"
        assert issues[0].capability == "moodle/course:create"
        assert "course:create" in issues[0].admin_action

    @pytest.mark.anyio
    async def test_missing_page_function_reports_content_api_unavailable(self):
        info = {
            **DEFAULT_SITE_INFO,
            "functions": [
                name
                for name in ALL_FUNCTIONS
                if name != "local_ai_course_engine_add_page"
            ],
        }
        client = FakeClient(site_info=info)
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.CONTENT_API_UNAVAILABLE)
        assert issues[0].ws_function == "local_ai_course_engine_add_page"
        assert issues[0].capability == "mod/page:addinstance"
        assert "ai_course_engine plugin" in issues[0].admin_action


class TestContentPluginFunctions:
    @pytest.mark.anyio
    async def test_missing_plugin_function_reports_content_api_unavailable(self):
        info = {
            **DEFAULT_SITE_INFO,
            "functions": [
                name
                for name in ALL_FUNCTIONS
                if name != "local_ai_course_engine_update_section"
            ],
        }
        client = FakeClient(site_info=info)
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.CONTENT_API_UNAVAILABLE)
        assert len(issues) == 1
        assert issues[0].ws_function == "local_ai_course_engine_update_section"
        assert issues[0].capability == "moodle/course:update"
        assert "core_course_edit_section" in issues[0].admin_action


class TestInvalidCategory:
    @pytest.mark.anyio
    async def test_empty_category_reports_invalid_category(self):
        client = FakeClient(categories=[])
        result = await run_readiness_check(client, category_id=7)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.INVALID_CATEGORY)
        assert len(issues) == 1
        assert issues[0].ws_function == "core_course_get_categories"
        assert "7" in issues[0].admin_action
        assert result.category_found is False


class TestAuthAndTransient:
    @pytest.mark.anyio
    async def test_403_token_failure_reports_invalid_token(self):
        client = FakeClient(
            site_info_error=MoodleIntegrationError(
                "Moodle rejected the web service token.",
                details={
                    "function": "core_webservice_get_site_info",
                    "http_status": 403,
                },
            )
        )
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.INVALID_TOKEN)
        assert len(issues) == 1
        assert "token" in issues[0].admin_action.lower()
        assert result.functions_available == []

    @pytest.mark.anyio
    async def test_invalidtoken_errorcode_reports_invalid_token(self):
        client = FakeClient(
            site_info_error=MoodleIntegrationError(
                "The token is invalid.",
                details={
                    "function": "core_webservice_get_site_info",
                    "errorcode": "invalidtoken",
                },
            )
        )
        result = await run_readiness_check(client, category_id=1)

        assert _finding_issue(result, MoodleIssueKind.INVALID_TOKEN)

    @pytest.mark.anyio
    async def test_accessexception_reports_missing_capability(self):
        client = FakeClient(
            site_info_error=MoodleIntegrationError(
                "Access exception.",
                details={
                    "function": "core_webservice_get_site_info",
                    "errorcode": "accessexception",
                },
            )
        )
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.MISSING_CAPABILITY)
        assert len(issues) == 1
        assert issues[0].ws_function == "core_webservice_get_site_info"
        assert "core_course_get_contents" in issues[0].admin_action

    @pytest.mark.anyio
    async def test_transport_timeout_reports_transient_failure(self):
        client = FakeClient(site_info_error=_transport_error())
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        issues = _finding_issue(result, MoodleIssueKind.TRANSIENT_FAILURE)
        assert len(issues) == 1
        assert issues[0].recoverable is True

    @pytest.mark.anyio
    async def test_unknown_error_reports_auth_failure(self):
        client = FakeClient(
            site_info_error=MoodleIntegrationError(
                "Moodle returned a non-JSON response.",
                details={"function": "core_webservice_get_site_info"},
            )
        )
        result = await run_readiness_check(client, category_id=1)

        assert _finding_issue(result, MoodleIssueKind.AUTH_FAILURE)


class TestCategoryProbeFailures:
    @pytest.mark.anyio
    async def test_transient_category_error_still_reported(self):
        def fail(**kwargs):
            raise _transport_error()

        client = FakeClient()
        client.get_categories = fail
        result = await run_readiness_check(client, category_id=1)

        assert result.ready is False
        assert _finding_issue(result, MoodleIssueKind.TRANSIENT_FAILURE)


def _finding_check(result, label):
    return [check for check in result.checks if check.label == label][0]


class TestReadinessChecks:
    @pytest.mark.anyio
    async def test_successful_preflight_reports_ok_checks(self):
        client = FakeClient()
        result = await run_readiness_check(client, category_id=1)

        connection = _finding_check(result, "Moodle connection & API access")
        assert connection.status.value == "ok"
        assert result.checks[1].label == "Web service token authentication"
        assert result.checks[1].status.value == "ok"
        category = _finding_check(result, "Course category")
        assert category.status.value == "ok"
        assert category.verification.value == "direct"
        function_check = _finding_check(
            result, "Web service function core_course_create_courses"
        )
        assert function_check.status.value == "ok"
        capability_check = _finding_check(
            result, "Capability moodle/course:create"
        )
        assert capability_check.status.value == "ok"
        assert capability_check.verification.value == "inferred"
        assert "cannot be queried directly" in capability_check.detail

    @pytest.mark.anyio
    async def test_capability_check_is_inferred_and_honest(self):
        info = {
            **DEFAULT_SITE_INFO,
            "functions": [
                name
                for name in ALL_FUNCTIONS
                if name != "core_course_create_courses"
            ],
        }
        client = FakeClient(site_info=info)
        result = await run_readiness_check(client, category_id=1)

        capability_check = _finding_check(
            result, "Capability moodle/course:create"
        )
        assert capability_check.status.value == "error"
        assert capability_check.verification.value == "inferred"
        assert capability_check.capability == "moodle/course:create"
        assert "inferred" in capability_check.detail.lower()
        function_check = _finding_check(
            result, "Web service function core_course_create_courses"
        )
        assert function_check.status.value == "error"
        assert function_check.verification.value == "direct"

    @pytest.mark.anyio
    async def test_auth_failure_marks_unreachable_checks_as_not_verifiable(self):
        client = FakeClient(
            site_info_error=MoodleIntegrationError(
                "Moodle rejected the web service token.",
                details={
                    "function": "core_webservice_get_site_info",
                    "http_status": 403,
                },
            )
        )
        result = await run_readiness_check(client, category_id=1)

        connection = _finding_check(result, "Moodle connection & API access")
        assert connection.status.value == "error"
        authentication = _finding_check(
            result, "Web service token authentication"
        )
        assert authentication.status.value == "error"
        assert authentication.verification.value == "direct"
        category = _finding_check(result, "Course category")
        assert category.status.value == "warning"
        assert category.verification.value == "not_verifiable"
        function_check = _finding_check(
            result, "Web service function core_course_create_courses"
        )
        assert function_check.verification.value == "not_verifiable"

    @pytest.mark.anyio
    async def test_invalid_category_reports_error_check(self):
        client = FakeClient(categories=[])
        result = await run_readiness_check(client, category_id=7)

        category = _finding_check(result, "Course category")
        assert category.status.value == "error"
        assert category.verification.value == "direct"
        assert result.ready is False

    @pytest.mark.anyio
    async def test_not_configured_reports_single_error_check(self):
        result = await run_readiness_check(None, category_id=1)

        assert len(result.checks) == 1
        assert result.checks[0].status.value == "error"
        assert "MOODLE_URL" in result.checks[0].detail