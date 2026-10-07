"""Ingestion job creation, status, and cancellation endpoints."""

from __future__ import annotations

import uuid
from contextlib import suppress

from app.core.dependencies import get_database_session, get_redis_client
from app.core.exceptions import DocumentNotFound, IngestionJobNotFound
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.ingestion_jobs import IngestionJobRepository
from app.models.ingestion_job import IngestionJob
from app.schemas.ingestion import (
    IngestionJobCreate,
    IngestionJobCreateResponse,
    IngestionJobRead,
)
from app.services.ingestion.job_queue import enqueue, remove_from_queue
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/jobs", response_model=IngestionJobCreateResponse, status_code=201)
async def create_ingestion_job(
    payload: IngestionJobCreate,
    session: AsyncSession = Depends(get_database_session),
    redis_client: Redis = Depends(get_redis_client),
) -> IngestionJobCreateResponse:
    """
    Create (or return an existing) ingestion job for a document.

    If a non-terminal job already exists for this document, it is
    returned as-is (created=False) rather than creating a duplicate.
    Otherwise a new job is created, persisted, and enqueued for the
    worker to pick up (created=True).
    """
    document_repository = DocumentRepository(session)
    document = await document_repository.get_by_id(payload.document_id)

    if document is None:
        raise DocumentNotFound(f"Document {payload.document_id} was not found.")

    job_repository = IngestionJobRepository(session)
    existing_job = await job_repository.get_active_for_document(payload.document_id)

    if existing_job is not None:
        return IngestionJobCreateResponse(
            job=IngestionJobRead.model_validate(existing_job),
            created=False,
        )

    job = IngestionJob(document_id=payload.document_id)
    await job_repository.add(job)
    await job_repository.commit()

    await enqueue(redis_client, str(job.id))

    return IngestionJobCreateResponse(
        job=IngestionJobRead.model_validate(job),
        created=True,
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobRead)
async def get_ingestion_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> IngestionJobRead:
    """Fetch the current status of an ingestion job."""
    job_repository = IngestionJobRepository(session)
    job = await job_repository.get_by_id(job_id)

    if job is None:
        raise IngestionJobNotFound(f"Ingestion job {job_id} was not found.")

    return IngestionJobRead.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=IngestionJobRead)
async def cancel_ingestion_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
    redis_client: Redis = Depends(get_redis_client),
) -> IngestionJobRead:
    """
    Cancel an ingestion job.

    Raises InvalidStateTransition (409) if the job is already in a
    terminal state (COMPLETED or CANCELLED). Best-effort removes the
    job from the Redis queue so a worker does not later dequeue it; a
    worker already mid-processing this job runs to completion and its
    final transition then fails validation, which the worker logs and
    drops without disturbing the loop.
    """
    job_repository = IngestionJobRepository(session)
    job = await job_repository.get_by_id(job_id)

    if job is None:
        raise IngestionJobNotFound(f"Ingestion job {job_id} was not found.")

    await job_repository.cancel(job)
    await job_repository.commit()

    with suppress(redis_client.ConnectionError):
        await remove_from_queue(redis_client, str(job_id))

    return IngestionJobRead.model_validate(job)
