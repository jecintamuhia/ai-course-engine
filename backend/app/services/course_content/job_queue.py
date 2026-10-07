"""Reliable Redis-backed queue for bulk course-content generation jobs.

Deliberately separate from the ingestion queue (``app.services.ingestion
.job_queue``): a full 16-week generation run occupies a worker for a long
time, and must never delay document ingestion or starve it of a consumer.
"""

from __future__ import annotations

import asyncio
import time

from redis.asyncio import Redis

READY_KEY = "content_generation:jobs:ready"
PROCESSING_KEY = "content_generation:jobs:processing"
DELAYED_KEY = "content_generation:jobs:delayed"


async def enqueue(redis_client: Redis, job_id: str) -> None:
    """Push a job onto the ready queue."""
    await redis_client.lpush(READY_KEY, job_id)


async def schedule_retry(
    redis_client: Redis, job_id: str, delay_seconds: float
) -> None:
    """Schedule a job to become ready again after delay_seconds."""
    await redis_client.zadd(DELAYED_KEY, {job_id: time.time() + delay_seconds})


async def promote_due_delayed_jobs(redis_client: Redis) -> int:
    """Move delayed jobs whose retry time has passed onto the ready queue."""
    now = time.time()
    due_job_ids = await redis_client.zrangebyscore(DELAYED_KEY, 0, now)

    for job_id in due_job_ids:
        if await redis_client.zrem(DELAYED_KEY, job_id):
            await redis_client.lpush(READY_KEY, job_id)

    return len(due_job_ids)


async def dequeue(redis_client: Redis, poll_timeout: int = 5) -> str | None:
    """
    Pop a job from the ready queue onto the processing list.

    Uses RPOPLPUSH (a poll loop, for the same redis-py blocking-wait
    reason documented in the ingestion queue) so a job stays visible in
    the processing list if the worker dies mid-run instead of vanishing.
    """
    deadline = time.monotonic() + poll_timeout

    while True:
        job_id = await redis_client.rpoplpush(READY_KEY, PROCESSING_KEY)
        if job_id is not None:
            return job_id

        if time.monotonic() >= deadline:
            return None

        await asyncio.sleep(0.5)


async def ack(redis_client: Redis, job_id: str) -> None:
    """Remove a job from the processing list once handling is complete."""
    await redis_client.lrem(PROCESSING_KEY, 0, job_id)
