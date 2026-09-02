"""Pydantic schemas for document structure (chapters and sections)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class SectionRead(BaseModel):
    """Public representation of a detected section."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str | None
    title: str
    start_page: int
    end_page: int
    order_index: int


class ChapterRead(BaseModel):
    """Public representation of a detected chapter, with its sections."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: str | None
    title: str
    start_page: int
    end_page: int
    order_index: int
    sections: list[SectionRead] = []


class DocumentStructureResponse(BaseModel):
    """Full detected structure for a document."""

    document_id: uuid.UUID
    chapters: list[ChapterRead]