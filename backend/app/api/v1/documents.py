"""Document upload and retrieval endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_database_session
from app.core.exceptions import DocumentNotFound
from app.db.repositories.documents import DocumentRepository
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.document_storage import DocumentStorageService

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_storage_service(
    session: AsyncSession = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentStorageService:
    """Construct a request-scoped document storage service."""
    repository = DocumentRepository(session)
    return DocumentStorageService(repository, settings)


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    replaces_document_id: uuid.UUID | None = Form(default=None),
    service: DocumentStorageService = Depends(get_document_storage_service),
) -> DocumentUploadResponse:
    """
    Upload a source document (PDF or DOCX).

    If the uploaded content is byte-for-byte identical to an existing
    latest-version document, no new file is written and the existing
    document is returned with ``is_duplicate=True``. Passing
    ``replaces_document_id`` always creates a new version, linked to the
    document it replaces.
    """
    document, is_duplicate = await service.store_upload(
        file, replaces_document_id=replaces_document_id
    )

    return DocumentUploadResponse(
        document=DocumentRead.model_validate(document),
        is_duplicate=is_duplicate,
    )


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> DocumentRead:
    """Fetch metadata for a single document by ID."""
    repository = DocumentRepository(session)
    document = await repository.get_by_id(document_id)

    if document is None:
        raise DocumentNotFound(f"Document {document_id} was not found.")

    return DocumentRead.model_validate(document)