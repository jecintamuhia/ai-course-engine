"""Resolve published Moodle Page bodies for course modules.

``core_course_get_contents`` returns a module's *file* contents (for a
Page activity, a download link to the generated ``index.html``), not the
page body itself. The page body is exposed by the standard
``mod_page_get_pages_by_courses`` web service, keyed by course-module id.

Reading the body is what makes lesson content and the embedded lesson
identity marker available to the portals and to post-publish
verification. When the function is unavailable (for example it was not
added to the token's external service) the body map is simply empty;
callers keep whatever content core already returned and report a clear
error at the point where a body is actually required.
"""

from __future__ import annotations

import logging

from app.core.exceptions import MoodleIntegrationError
from app.services.moodle.client import MoodleClient

logger = logging.getLogger(__name__)

#: ``{course-module id: (content, contentformat)}``
PageBodies = dict[int, tuple[str | None, int | None]]


async def load_page_bodies(
    client: MoodleClient, course_id: int
) -> PageBodies:
    """
    Return the published Page bodies for a course, keyed by module id.

    Never raises for an unavailable/unsupported function: an empty map
    means the bodies could not be read, and the caller decides how to
    surface that. Transport and token failures are logged with enough
    context to diagnose the Moodle configuration.
    """
    try:
        data = await client.get_pages_by_courses(course_id)
    except MoodleIntegrationError as exc:
        logger.warning(
            "Could not read Moodle page bodies course_id=%s reason=%s",
            course_id,
            exc.message,
        )
        return {}

    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return {}

    bodies: PageBodies = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        cmid = page.get("coursemodule")
        if not isinstance(cmid, int):
            continue
        content = page.get("content")
        content_format = page.get("contentformat")
        bodies[cmid] = (
            content if isinstance(content, str) else None,
            content_format if isinstance(content_format, int) else None,
        )
    return bodies


def apply_page_bodies(sections: list[dict], bodies: PageBodies) -> None:
    """
    Overlay resolved Page bodies onto ``core_course_get_contents`` data.

    Only Page modules present in ``bodies`` are touched, and only when a
    body string was returned; existing core content is never erased with
    ``None``. Modules are mutated in place so the rest of the mapping
    code continues to read ``contents[0].content``.
    """
    if not bodies:
        return
    for section in sections or []:
        if not isinstance(section, dict):
            continue
        for module in section.get("modules") or []:
            if not isinstance(module, dict):
                continue
            if module.get("modname") != "page":
                continue
            cmid = module.get("id")
            if not isinstance(cmid, int) or cmid not in bodies:
                continue
            content, content_format = bodies[cmid]
            if content is None:
                continue
            module["contents"] = [
                {"content": content, "contentformat": content_format}
            ]
