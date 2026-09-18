"""Permissive Moodle connection-status computation.

Returns a status dictionary even when Moodle is unreachable (network
failures become ``error`` text and ``connected=false``), so callers like
the status endpoint and the dashboard never fail because of Moodle being
down or unconfigured.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.moodle.client import MoodleClient

logger = get_logger(__name__)


async def connection_status(
    settings: Settings,
    client: MoodleClient | None,
) -> dict[str, Any]:
    """Build the Moodle connection status for the given settings/client."""
    if client is None:
        return {
            "configured": False,
            "moodle_url": settings.moodle_url,
            "connected": False,
            "site_name": None,
            "site_url": None,
            "api_version": None,
            "username": None,
            "error": None,
        }

    try:
        info = await client.get_site_info()
    except Exception as exc:  # noqa: BLE001 - permissive status surface
        logger.warning("Moodle status check failed: %s", exc)
        return {
            "configured": True,
            "moodle_url": settings.moodle_url,
            "connected": False,
            "site_name": None,
            "site_url": None,
            "api_version": None,
            "username": None,
            "error": str(exc),
        }

    return {
        "configured": True,
        "moodle_url": settings.moodle_url,
        "connected": True,
        "site_name": info.get("sitename"),
        "site_url": info.get("siteurl"),
        "api_version": info.get("version"),
        "username": info.get("username"),
        "error": None,
    }
