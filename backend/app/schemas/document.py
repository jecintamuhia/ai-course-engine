"""Pydantic schemas for document resources."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    """Public representation of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256_hash: str
    version_number: int
    is_latest_version: bool
    previous_version_id: uuid.UUID | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DocumentUploadResponse(BaseModel):
    """Response returned after a document upload."""

    document: DocumentRead
    is_duplicate: bool