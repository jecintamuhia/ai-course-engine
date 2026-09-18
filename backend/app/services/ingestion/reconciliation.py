"""Reconciliation for ingestion jobs stuck in PENDING before enqueue."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db.repositories.ingestion_jobs import IngestionJobRepository
from app.services.ingestion.job_queue import enqueue, is_queued
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

DEFAULT_STALE_JOB_AGE_SECONDS = 300


async def reconcile_stale_jobs(
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    max_age_seconds: int = DEFAULT_STALE_JOB_AGE_SECONDS,
) -> int:
    """
    Re-enqueue jobs stuck in PENDING for longer than max_age_seconds.

    A job can be stuck in PENDING when it was committed to the database
    but never pushed onto the Redis queue (enqueue failure, or a worker
    crash before its first state transition). Jobs already present in
    the ready, processing, or delayed sets are left untouched so they
    are never duplicated.
    """
    older_than = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    requeued = 0

    async with session_factory() as session:
        repository = IngestionJobRepository(session)
        stale_jobs = await repository.list_stale_pending(older_than)

        for job in stale_jobs:
            job_id = str(job.id)

            if await is_queued(redis_client, job_id):
                continue

            await enqueue(redis_client, job_id)
            requeued += 1

    return requeued