"""Reliable Redis-backed queue for ingestion jobs, with delayed retries."""

from __future__ import annotations

import asyncio
import time

from redis.asyncio import Redis

READY_KEY = "ingestion:jobs:ready"
PROCESSING_KEY = "ingestion:jobs:processing"
DELAYED_KEY = "ingestion:jobs:delayed"

DEFAULT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_BACKOFF_MAX_SECONDS = 300.0


async def enqueue(redis_client: Redis, job_id: str) -> None:
    """Push a job onto the ready queue."""
    await redis_client.lpush(READY_KEY, job_id)


async def schedule_retry(
    redis_client: Redis, job_id: str, delay_seconds: float
) -> None:
    """Schedule a job to become ready again after delay_seconds."""
    ready_at = time.time() + delay_seconds
    await redis_client.zadd(DELAYED_KEY, {job_id: ready_at})


async def promote_due_delayed_jobs(redis_client: Redis) -> int:
    """
    Move any delayed jobs whose retry time has passed into the ready
    queue. Returns the number of jobs promoted.
    """
    now = time.time()
    due_job_ids = await redis_client.zrangebyscore(DELAYED_KEY, 0, now)

    for job_id in due_job_ids:
        removed = await redis_client.zrem(DELAYED_KEY, job_id)
        if removed:
            await redis_client.lpush(READY_KEY, job_id)

    return len(due_job_ids)


async def dequeue(
    redis_client: Redis, poll_timeout: int = 5
) -> str | None:
    """
    Reliably pop a job from the ready queue onto the processing list.

    RPOPLPUSH (rather than a plain pop) means a job remains visible in
    the processing list if the worker crashes mid-handling, rather than
    being silently lost. Uses a non-blocking poll loop instead of
    BRPOPLPUSH, because redis-py 8's client-side handling of blocking
    waits aborts early on some environments; a poll loop is deterministic
    and honors the same server-side timeout.
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


async def remove_from_queue(redis_client: Redis, job_id: str) -> None:
    """
    Best-effort removal of a job from every queue structure (ready,
    processing, and delayed). Used when cancelling a job so a worker
    does not later dequeue it and try to process a cancelled job.
    """
    await redis_client.lrem(READY_KEY, 0, job_id)
    await redis_client.lrem(PROCESSING_KEY, 0, job_id)
    await redis_client.zrem(DELAYED_KEY, job_id)


async def is_queued(redis_client: Redis, job_id: str) -> bool:
    """Return whether a job id is present in the ready, processing, or delayed sets."""
    if job_id in await redis_client.lrange(PROCESSING_KEY, 0, -1):
        return True

    if job_id in await redis_client.lrange(READY_KEY, 0, -1):
        return True

    return await redis_client.zscore(DELAYED_KEY, job_id) is not None


def compute_backoff_seconds(
    attempt: int,
    *,
    base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
    max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS,
) -> float:
    """Exponential backoff: base * 2^(attempt-1), capped at max_seconds."""
    delay = base_seconds * (2 ** (attempt - 1))
    return min(delay, max_seconds)