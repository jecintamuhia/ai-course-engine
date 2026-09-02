"""Pydantic schemas for page resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PageRead(BaseModel):
    """Public representation of an extracted page."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    page_number: int
    normalized_text: str
    char_count: int
    created_at: datetime


class PageExtractionResponse(BaseModel):
    """Response returned after triggering extraction for a document."""

    document_id: uuid.UUID
    page_count: int
    pages: list[PageRead]