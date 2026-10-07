"""Unit tests for the Redis-backed ingestion job queue."""

from __future__ import annotations

import pytest
from app.services.ingestion.job_queue import (
    PROCESSING_KEY,
    READY_KEY,
    ack,
    dequeue,
    enqueue,
    is_queued,
    promote_due_delayed_jobs,
    schedule_retry,
)
from fakeredis.aioredis import FakeRedis


@pytest.fixture
async def redis_client():
    client = FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_enqueue_and_dequeue_moves_job_to_processing(redis_client) -> None:
    await enqueue(redis_client, "job-1")

    job_id = await dequeue(redis_client, poll_timeout=1)

    assert job_id == "job-1"
    assert await redis_client.llen(PROCESSING_KEY) == 1


@pytest.mark.asyncio
async def test_ack_removes_job_from_processing(redis_client) -> None:
    await enqueue(redis_client, "job-1")
    await dequeue(redis_client, poll_timeout=1)

    await ack(redis_client, "job-1")

    assert await redis_client.llen(PROCESSING_KEY) == 0


@pytest.mark.asyncio
async def test_dequeue_returns_none_when_queue_empty(redis_client) -> None:
    job_id = await dequeue(redis_client, poll_timeout=1)
    assert job_id is None


@pytest.mark.asyncio
async def test_delayed_job_not_promoted_before_due(redis_client) -> None:
    await schedule_retry(redis_client, "job-2", delay_seconds=100)

    promoted = await promote_due_delayed_jobs(redis_client)

    assert promoted == 0
    assert await redis_client.llen(READY_KEY) == 0


@pytest.mark.asyncio
async def test_delayed_job_promoted_once_due(redis_client) -> None:
    await schedule_retry(redis_client, "job-3", delay_seconds=-1)

    promoted = await promote_due_delayed_jobs(redis_client)

    assert promoted == 1
    job_id = await dequeue(redis_client, poll_timeout=1)
    assert job_id == "job-3"


@pytest.mark.asyncio
async def test_is_queued_reflects_ready_processing_and_delayed(
    redis_client,
) -> None:
    await enqueue(redis_client, "job-ready")
    await enqueue(redis_client, "job-processing")
    await dequeue(redis_client, poll_timeout=1)

    assert await is_queued(redis_client, "job-ready")
    assert await is_queued(redis_client, "job-processing")
    assert not await is_queued(redis_client, "job-absent")


@pytest.mark.asyncio
async def test_is_queued_true_when_delayed(redis_client) -> None:
    await schedule_retry(redis_client, "job-delayed", delay_seconds=100)

    assert await is_queued(redis_client, "job-delayed")
