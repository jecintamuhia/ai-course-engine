"""Pydantic schemas for chunk resources."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class ChunkRead(BaseModel):
    """Public representation of a semantic chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    page_id: uuid.UUID
    chapter_id: uuid.UUID | None
    section_id: uuid.UUID | None
    document_index: int
    page_index: int
    content: str
    char_count: int
    content_hash: str


class ChunkingResponse(BaseModel):
    """Response returned after chunking a document."""

    document_id: uuid.UUID
    chunk_count: int
    chunks: list[ChunkRead]