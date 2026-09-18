"""Dashboard and document-overview aggregation services.

These services collect real, persisted processing state into the summary
shapes the web UI renders — no mocked data is ever presented.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.courses import CourseRepository
from app.db.repositories.curriculum import CurriculumRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.ingestion_jobs import IngestionJobRepository
from app.db.repositories.pages import PageRepository
from app.db.repositories.structure import StructureRepository
from app.db.repositories.topics import TopicRepository
from app.models.curriculum import CurriculumStatus

logger = get_logger(__name__)


class OverviewService:
    """Build per-document processing summaries and dashboard totals."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        page_repository: PageRepository,
        structure_repository: StructureRepository,
        chunk_repository: ChunkRepository,
        topic_repository: TopicRepository,
        curriculum_repository: CurriculumRepository,
        ingestion_job_repository: IngestionJobRepository,
        course_repository: CourseRepository,
    ) -> None:
        self._document_repository = document_repository
        self._page_repository = page_repository
        self._structure_repository = structure_repository
        self._chunk_repository = chunk_repository
        self._topic_repository = topic_repository
        self._curriculum_repository = curriculum_repository
        self._ingestion_job_repository = ingestion_job_repository
        self._course_repository = course_repository

    async def list_overviews(self, *, limit: int = 100) -> list[dict]:
        """
        Return the newest documents, each with its current processing
        counts and the latest ingestion job.
        """
        documents = await self._document_repository.list_latest()
        documents = documents[:limit]

        page_counts = await self._page_repository.count_by_document()
        chapter_counts = await self._structure_repository.count_by_document()
        chunk_counts = await self._chunk_repository.count_by_document()
        topic_counts = await self._topic_repository.count_by_document()
        curriculum_counts = await self._curriculum_repository.count_latest_by_document()

        overviews: list[dict] = []
        for document in documents:
            latest_job = await self._ingestion_job_repository.latest_by_document(
                document.id
            )
            overviews.append(
                {
                    "document": document,
                    "page_count": page_counts.get(document.id, 0),
                    "chapter_count": chapter_counts.get(document.id, 0),
                    "chunk_count": chunk_counts.get(document.id, 0),
                    "topic_count": topic_counts.get(document.id, 0),
                    "curriculum_count": curriculum_counts.get(document.id, 0),
                    "latest_job": latest_job,
                }
            )

        return overviews

    async def dashboard(self, *, moodle_status: dict | None = None) -> dict:
        """
        Return aggregate totals for the dashboard.

        ``moodle_status`` is the already-computed connection status; it
        is passed in so route handlers control how Moodle failures are
        represented (permissively, never causing the dashboard to fail).
        """
        documents = await self._document_repository.list_latest()
        in_progress = await self._ingestion_job_repository.count_in_progress()

        curricula = {
            "draft": (
                await self._curriculum_repository.count_by_status(
                    CurriculumStatus.DRAFT
                )
            ),
            "awaiting_review": (
                await self._curriculum_repository.count_by_status(
                    CurriculumStatus.AWAITING_REVIEW
                )
            ),
            "approved": (
                await self._curriculum_repository.count_by_status(
                    CurriculumStatus.APPROVED
                )
            ),
            "rejected": (
                await self._curriculum_repository.count_by_status(
                    CurriculumStatus.REJECTED
                )
            ),
            "published": (
                await self._curriculum_repository.count_by_status(
                    CurriculumStatus.PUBLISHED
                )
            ),
        }

        return {
            "documents_total": len(documents),
            "documents_processing": in_progress,
            "curricula_total": sum(curricula.values()),
            "curricula_pending_review": curricula["awaiting_review"],
            "curricula_approved": curricula["approved"],
            "curricula_published": curricula["published"],
            "courses_published": await self._course_repository.count_all(),
            "moodle": moodle_status,
        }
