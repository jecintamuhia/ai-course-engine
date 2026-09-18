"""Pydantic schemas for per-document processing overviews."""

from __future__ import annotations

from app.schemas.document import DocumentRead
from app.schemas.ingestion import IngestionJobRead
from pydantic import BaseModel


class DocumentOverview(BaseModel):
    """A document with a summary of its current processing state."""

    document: DocumentRead
    page_count: int = 0
    chapter_count: int = 0
    chunk_count: int = 0
    topic_count: int = 0
    curriculum_count: int = 0
    latest_job: IngestionJobRead | None = None


class DocumentOverviewListResponse(BaseModel):
    """Latest documents with their processing summaries."""

    documents: list[DocumentOverview]
