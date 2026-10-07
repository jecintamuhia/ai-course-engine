"""Bulk course-content generation: enqueue and inspect whole-curriculum runs.

A full 16-week run is thousands of LLM calls, so it cannot run inside a
request. The API only persists a ContentGenerationJob and hands it to the
content worker; progress is read back from the job row the worker commits
after every week.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import ContentGenerationNotAllowed, CurriculumNotFound
from app.core.logging import get_logger
from app.db.repositories.content_generation_jobs import (
    ContentGenerationJobRepository,
)
from app.db.repositories.curriculum import CurriculumRepository
from app.models.content_generation_job import ContentGenerationJob
from app.models.curriculum import CurriculumStatus
from app.services.course_content.job_queue import enqueue
from redis.asyncio import Redis

logger = get_logger(__name__)


class ContentGenerationService:
    """Creates and reports bulk lesson-generation jobs."""

    def __init__(
        self,
        curriculum_repository: CurriculumRepository,
        job_repository: ContentGenerationJobRepository,
        redis_client: Redis,
    ) -> None:
        self._curriculum_repository = curriculum_repository
        self._job_repository = job_repository
        self._redis_client = redis_client

    async def start(
        self,
        curriculum_id: uuid.UUID,
        *,
        rebuild_existing: bool = False,
        requested_by: uuid.UUID | None = None,
    ) -> tuple[ContentGenerationJob, bool]:
        """
        Enqueue a bulk run, or return the in-flight run if there is one.

        Returns ``(job, created)``. Idempotent: a curriculum that already
        has a PENDING/RUNNING job returns it with ``created=False`` rather
        than starting a second concurrent run over the same units.
        """
        curriculum = await self._curriculum_repository.get_by_id(curriculum_id)
        if curriculum is None:
            raise CurriculumNotFound(f"Curriculum {curriculum_id} was not found.")

        if curriculum.status not in (
            CurriculumStatus.APPROVED,
            CurriculumStatus.PUBLISHED,
        ):
            raise ContentGenerationNotAllowed(
                "Approve the curriculum before generating its lessons.",
                details={
                    "curriculum_id": str(curriculum_id),
                    "status": curriculum.status.value,
                },
            )

        was_published = curriculum.status == CurriculumStatus.PUBLISHED
        if was_published:
            # The Moodle course remains available, but the current
            # curriculum version is being edited and must pass lecturer
            # review, QA, and a new verified sync before it is PUBLISHED
            # again.
            curriculum.status = CurriculumStatus.APPROVED

        existing = await self._job_repository.get_active_for_curriculum(curriculum_id)
        if existing is not None:
            if was_published:
                await self._curriculum_repository.commit()
            return existing, False

        total_weeks = len(curriculum.units)
        job = ContentGenerationJob(
            curriculum_id=curriculum_id,
            total_weeks=total_weeks,
            rebuild_existing=rebuild_existing,
            requested_by=requested_by,
        )
        await self._job_repository.add(job)
        await self._job_repository.commit()

        await enqueue(self._redis_client, str(job.id))

        logger.info(
            "Enqueued bulk content generation job_id=%s curriculum_id=%s "
            "total_weeks=%s rebuild_existing=%s",
            job.id,
            curriculum_id,
            total_weeks,
            rebuild_existing,
        )
        return job, True

    async def get_latest(self, curriculum_id: uuid.UUID) -> ContentGenerationJob | None:
        """Return the most recent job for a curriculum, if any."""
        return await self._job_repository.latest_by_curriculum(curriculum_id)
