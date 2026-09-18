"""Dashboard and document-overview endpoints."""

from __future__ import annotations

from app.core.config import Settings
from app.core.dependencies import (
    get_app_settings,
    get_database_session,
)
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.ingestion_jobs import IngestionJobRepository
from app.db.repositories.pages import PageRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.schemas.dashboard import DashboardResponse
from app.services.moodle.client import MoodleClient
from app.services.moodle.status import connection_status
from app.services.overview import OverviewService
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["dashboard"])


def get_overview_service(
    session: AsyncSession = Depends(get_database_session),
) -> OverviewService:
    """Construct a request-scoped overview service."""
    return OverviewService(
        DocumentRepository(session),
        PageRepository(session),
        StructureRepository(session),
        ChunkRepository(session),
        TopicRepository(session),
        CurriculumRepository(session),
        IngestionJobRepository(session),
        CourseRepository(session),
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    request: Request,
    settings: Settings = Depends(get_app_settings),
    service: OverviewService = Depends(get_overview_service),
) -> DashboardResponse:
    """
    Return aggregate platform totals for the dashboard screen.

    Moodle status is included permissively: a down or unconfigured
    Moodle never prevents the dashboard from loading.
    """
    client: MoodleClient | None = request.app.state.moodle_client
    status = await connection_status(settings, client)
    stats = await service.dashboard(moodle_status=status)
    return DashboardResponse(**stats)
