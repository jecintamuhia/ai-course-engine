"""Unit tests for stale ingestion-job reconciliation."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from app.models.ingestion_job import IngestionState
from app.services.ingestion.job_queue import PROCESSING_KEY, READY_KEY
from app.services.ingestion.reconciliation import reconcile_stale_jobs
from fakeredis.aioredis import FakeRedis


@pytest.fixture
async def redis_client():
    client = FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


class _StaleJob:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.status = IngestionState.PENDING


class _FakeSession:
    def __init__(self, stale_jobs: list[_StaleJob]) -> None:
        self._stale_jobs = stale_jobs

    async def execute(self, stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self._stale_jobs
        return result

    async def commit(self) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        return False


async def test_reconcile_reenqueues_stale_pending(redis_client) -> None:
    stale_job = _StaleJob()
    factory = _FakeSessionFactory(_FakeSession([stale_job]))

    requeued = await reconcile_stale_jobs(redis_client, factory)

    assert requeued == 1
    assert await redis_client.lrange(READY_KEY, 0, -1) == [str(stale_job.id)]


async def test_reconcile_skips_job_already_in_processing(redis_client) -> None:
    stale_job = _StaleJob()
    factory = _FakeSessionFactory(_FakeSession([stale_job]))

    await redis_client.rpush(PROCESSING_KEY, str(stale_job.id))

    requeued = await reconcile_stale_jobs(redis_client, factory)

    assert requeued == 0
    assert await redis_client.llen(READY_KEY) == 0


async def test_reconcile_returns_zero_when_no_stale_jobs(redis_client) -> None:
    factory = _FakeSessionFactory(_FakeSession([]))

    requeued = await reconcile_stale_jobs(redis_client, factory)

    assert requeued == 0
    assert await redis_client.llen(READY_KEY) == 0
