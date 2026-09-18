"""Pydantic schemas for dashboard resources."""

from __future__ import annotations

from app.schemas.moodle import MoodleConnectionStatus
from pydantic import BaseModel


class DashboardResponse(BaseModel):
    """Aggregate processing totals for the dashboard screen."""

    documents_total: int
    documents_processing: int
    curricula_total: int
    curricula_pending_review: int
    curricula_approved: int
    curricula_published: int
    courses_published: int
    moodle: MoodleConnectionStatus | None = None
