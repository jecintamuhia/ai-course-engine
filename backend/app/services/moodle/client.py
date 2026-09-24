"""Moodle Web Services REST client.

Talks to a Moodle instance through its Web Services REST endpoint
(``/webservice/rest/server.php``) using a Web Service token for
authentication. The Moodle site must have a web service enabled and a
token with the required capabilities assigned to it.

Client operations are idempotent at the application level: the sync
service groups them into find-or-create flows so that publishing twice
does not create duplicate courses or sections.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from app.core.config import Settings
from app.core.exceptions import MoodleIntegrationError

logger = logging.getLogger(__name__)

MOODLE_FUNCTION_URL = "/webservice/rest/server.php"


class MoodleClient:
    """Thin, robust wrapper around the Moodle web services REST API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout_seconds
        self._http_client = http_client
        self._embedded_client = None if http_client is not None else httpx.AsyncClient()

    @property
    def base_url(self) -> str:
        """Return the configured Moodle base URL."""
        return self._base_url

    @property
    def _client(self) -> httpx.AsyncClient:
        """Return the shared or privately-owned HTTP client."""
        return (
            self._http_client
            if self._http_client is not None
            else self._embedded_client
        )

    async def aclose(self) -> None:
        """Close resources owned by this client (not injected ones)."""
        if self._http_client is not None:
            return
        if self._embedded_client is not None:
            await self._embedded_client.aclose()
            self._embedded_client = None

    async def _call(self, wsfunction: str, **params: Any) -> Any:
        """
        Execute a Moodle web service function.

        Moodle returns HTTP 200 with an ``exception`` field for
        application-level errors; HTTP 403 for expired/invalid tokens.
        Both are translated into MoodleIntegrationError.
        """
        payload: dict[str, Any] = {
            "moodlewsrestformat": "json",
            "wstoken": self._token,
            "wsfunction": wsfunction,
        }
        payload.update(params)

        try:
            response = await self._client.post(
                f"{self._base_url}{MOODLE_FUNCTION_URL}",
                data=payload,
                timeout=self._timeout,
            )
        except httpx.TransportError as exc:
            raise MoodleIntegrationError(
                f"Could not reach Moodle at {self._base_url}.",
                details={"function": wsfunction, "reason": str(exc)},
            ) from exc

        if response.status_code == 403:
            raise MoodleIntegrationError(
                "Moodle rejected the web service token (HTTP 403). "
                "Check MOODLE_URL and MOODLE_TOKEN.",
                details={"function": wsfunction, "http_status": 403},
            )

        if response.status_code >= 400:
            logger.warning(
                "Moodle request failed wsfunction=%s http_status=%s body=%r",
                wsfunction,
                response.status_code,
                response.text[:500],
            )
            raise MoodleIntegrationError(
                f"Moodle returned HTTP {response.status_code} for {wsfunction}.",
                details={
                    "function": wsfunction,
                    "http_status": response.status_code,
                },
            )

        try:
            data = response.json()
        except ValueError:
            logger.warning(
                "Moodle returned a non-JSON response wsfunction=%s body=%r",
                wsfunction,
                response.text[:500],
            )
            raise MoodleIntegrationError(
                "Moodle returned a non-JSON response.",
                details={"function": wsfunction},
            ) from None

        if isinstance(data, dict) and "exception" in data:
            raise MoodleIntegrationError(
                data.get("message") or "Moodle reported an error.",
                details={
                    "function": wsfunction,
                    "errorcode": data.get("errorcode"),
                    "exception": data.get("exception"),
                },
            )

        return data

    # ------------------------------------------------------------------
    # High-level typed operations
    # ------------------------------------------------------------------

    async def get_site_info(self) -> dict[str, Any]:
        """Return core_webservice_get_site_info for the configured token."""
        return await self._call("core_webservice_get_site_info")

    async def get_categories(
        self, *, category_id: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Return visible course categories (optionally a single category).

        Uses ``core_course_get_categories`` with an optional id criterion;
        an empty list means the requested category does not exist (or is
        not visible to this token).
        """
        params: dict[str, Any] = {}
        if category_id is not None:
            params["criteria[0][key]"] = "id"
            params["criteria[0][value]"] = category_id
        data = await self._call("core_course_get_categories", **params)
        return data if isinstance(data, list) else []

    async def find_course_by_idnumber(self, idnumber: str) -> dict[str, Any] | None:
        """Return the Moodle course matching the given idnumber, if any."""
        data = await self._call(
            "core_course_get_courses_by_field",
            field="idnumber",
            value=idnumber,
        )
        courses = data.get("courses", []) if isinstance(data, dict) else []
        return courses[0] if courses else None

    async def create_course(
        self,
        *,
        fullname: str,
        shortname: str,
        idnumber: str,
        category_id: int,
        summary: str,
        num_sections: int,
    ) -> dict[str, Any]:
        """Create a course and return the first created course object."""
        data = await self._call(
            "core_course_create_courses",
            **{
                "courses[0][fullname]": fullname,
                "courses[0][shortname]": shortname,
                "courses[0][categoryid]": category_id,
                "courses[0][idnumber]": idnumber,
                "courses[0][summary]": summary,
                "courses[0][summaryformat]": 1,
                "courses[0][format]": "topics",
                "courses[0][numsections]": num_sections,
            },
        )
        courses = data if isinstance(data, list) else []
        if not courses:
            raise MoodleIntegrationError(
                "Moodle reported course creation succeeded but returned "
                "no course object.",
            )
        return courses[0]

    async def update_course(self, course_id: int, **fields: Any) -> Any:
        """Update a course's mutable fields (fullname/shortname/summary)."""
        params: dict[str, Any] = {"courses[0][id]": course_id}
        for key, value in fields.items():
            params[f"courses[0][{key}]"] = value
        return await self._call("core_course_update_courses", **params)

    async def get_course_contents(self, course_id: int) -> list[Any]:
        """Return core_course_get_contents for a course (sections/modules)."""
        data = await self._call("core_course_get_contents", courseid=course_id)
        return data if isinstance(data, list) else []

    async def update_section(
        self,
        course_id: int,
        *,
        section_number: int,
        name: str,
        summary: str,
    ) -> Any:
        """
        Name and summarise a course section (creating it if needed).

        Standard Moodle web services cannot set a section name or summary
        (core_course_edit_section only changes visibility/marker/deletion),
        so this uses the ``local_ai_course_engine_update_section`` function
        provided by the bundled local Moodle plugin.
        """
        return await self._call(
            "local_ai_course_engine_update_section",
            courseid=course_id,
            section=section_number,
            name=name,
            summary=summary,
            summaryformat=1,
        )

    async def add_page_module(
        self,
        course_id: int,
        *,
        section_number: int,
        name: str,
        content_html: str,
    ) -> int | None:
        """
        Add a 'Page' activity module to a section; return its cm id.

        Core Moodle registers no web service that creates a module
        instance, so this uses the ``local_ai_course_engine_add_page``
        function provided by the bundled local Moodle plugin.
        """
        data = await self._call(
            "local_ai_course_engine_add_page",
            courseid=course_id,
            section=section_number,
            name=name,
            content=content_html,
            contentformat=1,
        )
        if isinstance(data, dict):
            return data.get("cmid")
        if isinstance(data, list) and data:
            first = data[0]
            return first.get("cmid") if isinstance(first, dict) else int(first)
        if isinstance(data, int):
            return data
        return None


def create_moodle_client(settings: Settings) -> MoodleClient | None:
    """
    Construct the MoodleClient from configuration.

    Returns None when Moodle is not configured (missing URL or token),
    so application startup never fails on absent Moodle credentials.
    """
    base_url = settings.moodle_url
    token = settings.moodle_token.get_secret_value()

    if not base_url or not token:
        return None

    return MoodleClient(
        base_url,
        token,
        timeout_seconds=settings.moodle_timeout_seconds,
    )
