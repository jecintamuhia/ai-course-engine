"""Pydantic schemas for ingestion job resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.ingestion_job import IngestionState
from pydantic import BaseModel, ConfigDict


class IngestionJobCreate(BaseModel):
    """Request body for creating an ingestion job."""

    document_id: uuid.UUID


class IngestionJobRead(BaseModel):
    """Public representation of an ingestion job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    status: IngestionState
    correlation_id: str
    attempt_count: int
    max_attempts: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class IngestionJobCreateResponse(BaseModel):
    """Response returned after requesting job creation."""

    job: IngestionJobRead
    created: bool
