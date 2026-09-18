"""Moodle preflight/readiness check.

Determines, using only read-only web service calls, whether the
configured Moodle instance is ready to publish a curriculum via the
sync service. Every check classifies the outcome into a stable
``MoodleIssueKind`` so the API response and the Publish UI can present a
structured, human-actionable report ("Moodle administrator action
required") instead of a raw error string.

Readiness is a pure inspection: it never writes to Moodle and never
modifies any curriculum or course record. If the check reports not-ready,
the publisher refuses to start, leaving the curriculum untouched.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import MoodleIntegrationError
from app.services.moodle.client import MoodleClient

# Required web service functions for publishing a curriculum, the Moodle
# capability each function's token user must hold, and the Moodle release
# that introduced the function (None = available in all supported
# releases). Missing a capability produces a MISSING_CAPABILITY issue;
# a function that predates the connected Moodle produces an
# UNSUPPORTED_FUNCTION issue.
FUNCTION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "core_webservice_get_site_info": {
        "capability": None,
        "since": None,
        "detail": "Identify the connected token and site.",
    },
    "core_course_get_categories": {
        "capability": None,
        "since": None,
        "detail": "Validate the target course category.",
    },
    "core_course_get_courses_by_field": {
        "capability": "moodle/course:view",
        "since": None,
        "detail": "Find an existing course by idnumber (idempotent reuse).",
    },
    "core_course_get_contents": {
        "capability": "moodle/course:view",
        "since": None,
        "detail": "Read course sections/modules for sync and verification.",
    },
    "core_course_create_courses": {
        "capability": "moodle/course:create",
        "since": None,
        "detail": "Create the Moodle course on first publish.",
    },
    "core_course_update_courses": {
        "capability": "moodle/course:update",
        "since": None,
        "detail": "Update course names/summary on re-publish.",
    },
    "core_course_create_sections": {
        "capability": "moodle/course:update",
        "since": "4.0",
        "detail": "Create weekly course sections.",
    },
    "core_course_update_sections": {
        "capability": "moodle/course:update",
        "since": "4.0",
        "detail": "Update weekly section names/summaries.",
    },
    "mod_page_add_instance": {
        "capability": "mod/page:addinstance",
        "since": None,
        "detail": "Add the weekly 'Page' activity resources.",
    },
}


class MoodleIssueKind(str, enum.Enum):
    """Stable classification of a Moodle readiness problem."""

    NOT_CONFIGURED = "not_configured"
    INVALID_PARAMETER = "invalid_parameter"
    INVALID_TOKEN = "invalid_token"
    AUTH_FAILURE = "auth_failure"
    MISSING_CAPABILITY = "missing_capability"
    UNSUPPORTED_FUNCTION = "unsupported_function"
    INVALID_CATEGORY = "invalid_category"
    TRANSIENT_FAILURE = "transient_failure"


@dataclass
class MoodleReadinessIssue:
    """A single actionable readiness problem."""

    kind: MoodleIssueKind
    message: str
    admin_action: str
    ws_function: str | None = None
    capability: str | None = None
    recoverable: bool = True


class MoodleCheckStatus(str, enum.Enum):
    """Status of a single preflight check item."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class MoodleCheckVerification(str, enum.Enum):
    """
    How a check outcome was established.

    ``direct`` means the check probed Moodle (or the application state
    directly) and observed the result. ``inferred`` means the outcome was
    derived from an indirect observation — the Moodle Web Services API
    does not expose capability checks, so capabilities are inferred from
    the web service function declaration. ``not_verifiable`` means the
    item cannot be confirmed through the API at all.
    """

    DIRECT = "direct"
    INFERRED = "inferred"
    NOT_VERIFIABLE = "not_verifiable"


@dataclass
class MoodleReadinessCheck:
    """A single named item in the readiness checklist."""

    label: str
    status: MoodleCheckStatus
    detail: str
    verification: MoodleCheckVerification
    ws_function: str | None = None
    capability: str | None = None


@dataclass
class MoodleReadinessResult:
    """Aggregate readiness report for the configured Moodle."""

    ready: bool
    configured: bool
    issues: list[MoodleReadinessIssue] = field(default_factory=list)
    checks: list[MoodleReadinessCheck] = field(default_factory=list)
    moodle_url: str | None = None
    site_name: str | None = None
    site_url: str | None = None
    api_version: str | None = None
    username: str | None = None
    functions_available: list[str] = field(default_factory=list)
    functions_required: list[str] = field(default_factory=list)
    capabilities_required: list[str] = field(default_factory=list)
    category_id: int | None = None
    category_found: bool | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def functions_required_names(self) -> list[str]:
        return list(FUNCTION_REQUIREMENTS)

    @property
    def capabilities_required_names(self) -> list[str]:
        return sorted(
            {
                requirement["capability"]
                for requirement in FUNCTION_REQUIREMENTS.values()
                if requirement["capability"] is not None
            }
        )

    @property
    def blocking_issues(self) -> list[MoodleReadinessIssue]:
        """Alias of ``issues`` (blocking issues that prevent publishing)."""
        return self.issues


def check_to_dict(check: MoodleReadinessCheck) -> dict[str, Any]:
    """Serialize a readiness check item into a JSON-safe dict."""
    return {
        "label": check.label,
        "status": check.status.value,
        "detail": check.detail,
        "verification": check.verification.value,
        "ws_function": check.ws_function,
        "capability": check.capability,
    }


def issue_to_dict(issue: MoodleReadinessIssue) -> dict[str, Any]:
    """Serialize a readiness issue into a JSON-safe dict."""
    return {
        "kind": issue.kind.value,
        "message": issue.message,
        "admin_action": issue.admin_action,
        "ws_function": issue.ws_function,
        "capability": issue.capability,
        "recoverable": issue.recoverable,
    }


async def run_readiness_check(
    client: MoodleClient | None,
    *,
    category_id: int,
) -> MoodleReadinessResult:
    """Inspect Moodle and report whether publishing can proceed."""
    functions_required = list(FUNCTION_REQUIREMENTS)
    capabilities_required = sorted(
        {
            requirement["capability"]
            for requirement in FUNCTION_REQUIREMENTS.values()
            if requirement["capability"] is not None
        }
    )

    if client is None:
        return MoodleReadinessResult(
            ready=False,
            configured=False,
            checks=[
                MoodleReadinessCheck(
                    label="Moodle configuration",
                    status=MoodleCheckStatus.ERROR,
                    detail=(
                        "MOODLE_URL and MOODLE_TOKEN are not set, so no "
                        "Moodle checks can be performed."
                    ),
                    verification=MoodleCheckVerification.DIRECT,
                )
            ],
            issues=[
                MoodleReadinessIssue(
                    kind=MoodleIssueKind.NOT_CONFIGURED,
                    message=(
                        "Moodle integration is not configured: MOODLE_URL and "
                        "MOODLE_TOKEN are not set."
                    ),
                    admin_action=(
                        "Set MOODLE_URL and MOODLE_TOKEN in the environment, "
                        "create a web service token with the required "
                        "capabilities, and restart the application."
                    ),
                    recoverable=True,
                )
            ],
            functions_required=functions_required,
            capabilities_required=capabilities_required,
            category_id=category_id,
        )

    issues: list[MoodleReadinessIssue] = []

    if not isinstance(category_id, int) or category_id < 1:
        issues.append(
            MoodleReadinessIssue(
                kind=MoodleIssueKind.INVALID_PARAMETER,
                ws_function="core_course_create_courses",
                message=(
                    f"The course category id must be a positive integer, got "
                    f"{category_id!r}."
                ),
                admin_action=(
                    "Set MOODLE_COURSE_CATEGORY_ID to a valid course category "
                    "id (or pass a valid category_id when publishing)."
                ),
                recoverable=True,
            )
        )

    try:
        info = await client.get_site_info()
    except MoodleIntegrationError as exc:
        issues.append(_classify_connectivity_issue(exc))
        return _result(
            ready=False,
            configured=True,
            issues=issues,
            client=client,
            functions_required=functions_required,
            capabilities_required=capabilities_required,
            category_id=category_id if isinstance(category_id, int) else None,
            checks=_connectivity_checks(
                first_issue=issues[0],
                functions_required=functions_required,
                capabilities_required=capabilities_required,
                category_id=category_id if isinstance(category_id, int) else None,
            ),
        )

    release = info.get("release") or ""
    site_major = _moodle_release_key(release)

    rendered = _render_functions(info)

    for name in functions_required:
        if name in rendered:
            continue
        requirement = FUNCTION_REQUIREMENTS[name]
        since = requirement["since"]
        if since and site_major is not None and site_major < _moodle_release_key(since):
            issues.append(
                MoodleReadinessIssue(
                    kind=MoodleIssueKind.UNSUPPORTED_FUNCTION,
                    ws_function=name,
                    capability=requirement["capability"],
                    message=(
                        f"{name} requires Moodle {since} or newer; the "
                        f"connected Moodle is {release or 'unknown'}."
                    ),
                    admin_action=(
                        "Upgrade the Moodle site to the required version, or "
                        "publish to a Moodle instance that supports this "
                        "web service function."
                    ),
                    recoverable=True,
                )
            )
        else:
            detail = requirement["detail"]
            message = (
                f"{name} is not exposed to the configured web service token. "
                f"{detail}"
            )
            issues.append(
                MoodleReadinessIssue(
                    kind=MoodleIssueKind.MISSING_CAPABILITY,
                    ws_function=name,
                    capability=requirement["capability"],
                    message=message,
                    admin_action=(
                        "In Moodle: Site administration → Plugins → Web "
                        "services → External services, add the required "
                        "functions to the token's service, and grant the "
                        "capabilities listed for it."
                        + (
                            f" Required capability: {requirement['capability']}."
                            if requirement["capability"] is not None
                            else ""
                        )
                    ),
                    recoverable=True,
                )
            )

    category_found = None
    if (
        isinstance(category_id, int)
        and category_id >= 1
        and "core_course_get_categories" in rendered
    ):
        try:
            categories = await client.get_categories(category_id=category_id)
        except MoodleIntegrationError as exc:
            issues.append(_classify_connectivity_issue(exc))
        else:
            category_found = bool(categories)
            if not category_found:
                issues.append(
                    MoodleReadinessIssue(
                        kind=MoodleIssueKind.INVALID_CATEGORY,
                        ws_function="core_course_get_categories",
                        message=(
                            f"Moodle course category {category_id} was not "
                            "found or is not visible to the web service token."
                        ),
                        admin_action=(
                            "Set MOODLE_COURSE_CATEGORY_ID to an existing, "
                            "visible course category id, or ask the Moodle "
                            "administrator to grant the token access to "
                            f"category {category_id}."
                        ),
                        recoverable=True,
                    )
                )

    return _result(
        ready=not issues,
        configured=True,
        issues=issues,
        client=client,
        site_info=info,
        functions_available=sorted(rendered),
        functions_required=functions_required,
        capabilities_required=capabilities_required,
        category_id=category_id if isinstance(category_id, int) else None,
        category_found=category_found,
        checks=_connected_checks(
            rendered=rendered,
            category_id=category_id if isinstance(category_id, int) else None,
            category_found=category_found,
            category_probe_attempted=(
                isinstance(category_id, int)
                and category_id >= 1
                and "core_course_get_categories" in rendered
            ),
        ),
    )


def _result(
    *,
    ready: bool,
    configured: bool,
    issues: list[MoodleReadinessIssue],
    client: MoodleClient | None,
    site_info: dict[str, Any] | None = None,
    functions_available: list[str] | None = None,
    functions_required: list[str],
    capabilities_required: list[str],
    category_id: int | None = None,
    category_found: bool | None = None,
    checks: list[MoodleReadinessCheck] | None = None,
) -> MoodleReadinessResult:
    return MoodleReadinessResult(
        ready=ready,
        configured=configured,
        issues=issues,
        checks=checks or [],
        moodle_url=getattr(client, "base_url", None),
        site_name=site_info.get("sitename") if site_info else None,
        site_url=site_info.get("siteurl") if site_info else None,
        api_version=(site_info.get("release") or None) if site_info else None,
        username=site_info.get("username") if site_info else None,
        functions_available=functions_available or [],
        functions_required=functions_required,
        capabilities_required=capabilities_required,
        category_id=category_id,
        category_found=category_found,
    )


def _connectivity_checks(
    *,
    first_issue: MoodleReadinessIssue,
    functions_required: list[str],
    capabilities_required: list[str],
    category_id: int | None,
) -> list[MoodleReadinessCheck]:
    """Build the checklist when Moodle could not be reached/authenticated."""
    transient_issue = first_issue.kind in (
        MoodleIssueKind.TRANSIENT_FAILURE,
        MoodleIssueKind.INVALID_PARAMETER,
    )
    checks: list[MoodleReadinessCheck] = [
        MoodleReadinessCheck(
            label="Moodle connection & API access",
            status=MoodleCheckStatus.ERROR,
            detail=(
                "Moodle could not be reached or did not respond. "
                "Readiness cannot be evaluated."
            ),
            verification=MoodleCheckVerification.DIRECT,
        ),
        MoodleReadinessCheck(
            label="Web service token authentication",
            status=(
                MoodleCheckStatus.WARNING
                if transient_issue
                else MoodleCheckStatus.ERROR
            ),
            detail=(
                "Cannot be confirmed while Moodle is unreachable."
                if transient_issue
                else "Moodle rejected the web service token."
            ),
            verification=(
                MoodleCheckVerification.NOT_VERIFIABLE
                if transient_issue
                else MoodleCheckVerification.DIRECT
            ),
        ),
        MoodleReadinessCheck(
            label="Course category",
            status=MoodleCheckStatus.WARNING,
            detail=(
                f"Category {category_id} was not checked because the "
                "connection/authentication failed."
            ),
            verification=MoodleCheckVerification.NOT_VERIFIABLE,
        ),
    ]
    checks.extend(
        MoodleReadinessCheck(
            label=f"Web service function {name}",
            status=MoodleCheckStatus.WARNING,
            detail="Not checked because the connection/authentication failed.",
            verification=MoodleCheckVerification.NOT_VERIFIABLE,
            ws_function=name,
        )
        for name in functions_required
    )
    checks.extend(
        MoodleReadinessCheck(
            label=f"Capability {capability}",
            status=MoodleCheckStatus.WARNING,
            detail="Not checked because the connection/authentication failed.",
            verification=MoodleCheckVerification.NOT_VERIFIABLE,
            capability=capability,
        )
        for capability in capabilities_required
    )
    return checks


def _connected_checks(
    *,
    rendered: list[str],
    category_id: int | None,
    category_found: bool | None,
    category_probe_attempted: bool,
) -> list[MoodleReadinessCheck]:
    """
    Build the checklist after a successful site-info handshake.

    Function checks reflect the functions directly declared in the
    token's web service. Capability checks are deliberately inferred
    rather than claimed as verified: the Moodle Web Services API does not
    expose a capability query, so a capability is marked present only
    when every function that requires it is declared.
    """
    checks: list[MoodleReadinessCheck] = [
        MoodleReadinessCheck(
            label="Moodle connection & API access",
            status=MoodleCheckStatus.OK,
            detail="Moodle responded to an API call.",
            verification=MoodleCheckVerification.DIRECT,
        ),
        MoodleReadinessCheck(
            label="Web service token authentication",
            status=MoodleCheckStatus.OK,
            detail="The token was accepted and identified a user.",
            verification=MoodleCheckVerification.DIRECT,
        ),
    ]

    if category_probe_attempted:
        checks.append(
            MoodleReadinessCheck(
                label="Course category",
                status=(
                    MoodleCheckStatus.OK
                    if category_found
                    else MoodleCheckStatus.ERROR
                ),
                detail=(
                    f"Category {category_id} exists and is visible to the token."
                    if category_found
                    else (
                        f"Category {category_id} was not found or is not "
                        "visible to the token."
                    )
                ),
                verification=MoodleCheckVerification.DIRECT,
            )
        )
    else:
        checks.append(
            MoodleReadinessCheck(
                label="Course category",
                status=(
                    MoodleCheckStatus.WARNING
                    if category_id is not None
                    else MoodleCheckStatus.OK
                ),
                detail=(
                    "Not checked: the function that lists categories is not "
                    "exposed to the token."
                    if category_id is not None
                    else "No target category configured."
                ),
                verification=MoodleCheckVerification.NOT_VERIFIABLE,
            )
        )

    checks.extend(
        MoodleReadinessCheck(
            label=f"Web service function {name}",
            status=(
                MoodleCheckStatus.OK
                if name in rendered
                else MoodleCheckStatus.ERROR
            ),
            detail=(
                "Declared in the token's web service."
                if name in rendered
                else "Not declared in the token's web service."
            ),
            verification=MoodleCheckVerification.DIRECT,
            ws_function=name,
        )
        for name in FUNCTION_REQUIREMENTS
    )

    for capability, names in _functions_by_capability().items():
        present = {name for name in names if name in rendered}
        if len(present) == len(names):
            status = MoodleCheckStatus.OK
            detail = (
                f"Inferred present: all functions requiring it "
                f"({', '.join(sorted(names))}) are declared."
            )
        elif not present:
            status = MoodleCheckStatus.ERROR
            detail = (
                f"Inferred missing: none of the functions requiring it "
                f"({', '.join(sorted(names))}) are declared."
            )
        else:
            status = MoodleCheckStatus.WARNING
            detail = (
                f"Inferred partially present: only "
                f"{', '.join(sorted(present))} of {', '.join(sorted(names))} "
                "are declared."
            )
        checks.append(
            MoodleReadinessCheck(
                label=f"Capability {capability}",
                status=status,
                detail=(
                    f"{detail} Capabilities cannot be queried directly via "
                    "the Moodle Web Services API; this is an inference from "
                    "the declared functions."
                ),
                verification=MoodleCheckVerification.INFERRED,
                capability=capability,
            )
        )
    return checks


def _functions_by_capability() -> dict[str, list[str]]:
    """Map each required capability to the functions that need it."""
    grouped: dict[str, list[str]] = {}
    for name, requirement in FUNCTION_REQUIREMENTS.items():
        capability = requirement["capability"]
        if capability is None:
            continue
        grouped.setdefault(capability, []).append(name)
    return grouped


def _render_functions(info: dict[str, Any]) -> list[str]:
    """Return the web service function names reported by Moodle."""
    raw = info.get("functions") or []
    names: list[str] = []
    for entry in raw:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if isinstance(name, str):
            names.append(name)
    return names


def _classify_connectivity_issue(exc: MoodleIntegrationError) -> MoodleReadinessIssue:
    """Map a MoodleIntegrationError to a stable readiness issue."""
    details = exc.details or {}
    http_status = details.get("http_status")
    errorcode = details.get("errorcode")
    function = details.get("function")

    if errorcode == "invalidtoken" or http_status == 403:
        return MoodleReadinessIssue(
            kind=MoodleIssueKind.INVALID_TOKEN,
            ws_function=function,
            message=(
                "Moodle rejected the web service token. The token is "
                "missing, invalid, or expired, or its access has been "
                "revoked."
            ),
            admin_action=(
                "In Moodle: Site administration → Plugins → Web services → "
                "Manage tokens, confirm the token exists, is enabled, and "
                "matches MOODLE_TOKEN. Re-issue the token if it is stale."
            ),
            recoverable=True,
        )

    reason = str(details.get("reason") or exc.message)
    lowered = reason.lower()
    transient_words = ("could not reach", "timeout", "timed out", "refused")
    if any(word in lowered for word in transient_words):
        return MoodleReadinessIssue(
            kind=MoodleIssueKind.TRANSIENT_FAILURE,
            ws_function=function,
            message=(
                "Moodle could not be reached or timed out. This is usually "
                "a transient network/availability problem."
            ),
            admin_action=(
                "Confirm the Moodle site is up and reachable from this "
                "server, then retry the readiness check."
            ),
            recoverable=True,
        )

    return MoodleReadinessIssue(
        kind=MoodleIssueKind.AUTH_FAILURE,
        ws_function=function,
        message=f"Moodle refused the request: {exc.message}",
        admin_action=(
            "Verify MOODLE_URL and MOODLE_TOKEN, and confirm the web service "
            "is enabled for the token's user in Moodle."
        ),
        recoverable=True,
    )


_RELEASE_PATTERN = re.compile(r"(\d+)\.(\d+)")


def _moodle_release_key(release: str) -> tuple[int, int] | None:
    """Parse '4.5.2 (Build: 2024)' / '4.5.1' into a comparable (major, minor)."""
    match = _RELEASE_PATTERN.search(str(release or ""))
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))