"""Document upload, retrieval, extraction, structure, and chunking endpoints."""

from __future__ import annotations

import uuid

from app.api.v1.overview import get_overview_service
from app.core.config import Settings
from app.core.dependencies import get_app_settings, get_database_session
from app.core.exceptions import DocumentNotFound
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.pages import PageRepository
from app.db.repositories.structure import StructureRepository
from app.schemas.chunk import ChunkingResponse, ChunkRead
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.schemas.document_overview import (
    DocumentOverview,
    DocumentOverviewListResponse,
)
from app.schemas.ingestion import IngestionJobRead
from app.schemas.page import PageExtractionResponse, PageRead
from app.schemas.structure import ChapterRead, DocumentStructureResponse
from app.services.document_storage import DocumentStorageService
from app.services.ingestion.service import IngestionService
from app.services.overview import OverviewService
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/documents", tags=["documents"])


def get_document_storage_service(
    session: AsyncSession = Depends(get_database_session),
    settings: Settings = Depends(get_app_settings),
) -> DocumentStorageService:
    """Construct a request-scoped document storage service."""
    repository = DocumentRepository(session)
    return DocumentStorageService(repository, settings)


def get_ingestion_service(
    session: AsyncSession = Depends(get_database_session),
) -> IngestionService:
    """Construct a request-scoped ingestion service."""
    document_repository = DocumentRepository(session)
    page_repository = PageRepository(session)
    structure_repository = StructureRepository(session)
    chunk_repository = ChunkRepository(session)
    return IngestionService(
        document_repository,
        page_repository,
        structure_repository,
        chunk_repository,
    )


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


@router.get("", response_model=DocumentOverviewListResponse)
async def list_documents(
    service: OverviewService = Depends(get_overview_service),
) -> DocumentOverviewListResponse:
    """
    List latest documents with their current processing counts.

    Returns each document alongside page, chapter, chunk, topic and
    curriculum counts, plus the latest ingestion job if one exists.
    This is the primary data source for the documents screen.
    """
    overviews = await service.list_overviews(limit=100)
    return DocumentOverviewListResponse(
        documents=[
            DocumentOverview(
                document=DocumentRead.model_validate(o["document"]),
                page_count=o["page_count"],
                chapter_count=o["chapter_count"],
                chunk_count=o["chunk_count"],
                topic_count=o["topic_count"],
                curriculum_count=o["curriculum_count"],
                latest_job=(
                    None
                    if o["latest_job"] is None
                    else IngestionJobRead.model_validate(o["latest_job"])
                ),
            )
            for o in overviews
        ]
    )


@router.get("/{document_id}/overview", response_model=DocumentOverview)
async def get_document_overview(
    document_id: uuid.UUID,
    service: OverviewService = Depends(get_overview_service),
) -> DocumentOverview:
    """Return the processing summary for a single document."""
    overviews = await service.list_overviews(limit=1000000)
    for overview in overviews:
        if overview["document"].id == document_id:
            return DocumentOverview(
                document=DocumentRead.model_validate(overview["document"]),
                page_count=overview["page_count"],
                chapter_count=overview["chapter_count"],
                chunk_count=overview["chunk_count"],
                topic_count=overview["topic_count"],
                curriculum_count=overview["curriculum_count"],
                latest_job=(
                    None
                    if overview["latest_job"] is None
                    else IngestionJobRead.model_validate(overview["latest_job"])
                ),
            )

    raise DocumentNotFound(f"Document {document_id} was not found.")


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


@router.post(
    "/{document_id}/extract",
    response_model=PageExtractionResponse,
)
async def extract_document(
    document_id: uuid.UUID,
    service: IngestionService = Depends(get_ingestion_service),
) -> PageExtractionResponse:
    """
    Extract text from a document's pages.

    Runs synchronously for now. Re-running this for a document replaces
    any previously extracted pages rather than duplicating them.
    """
    pages = await service.extract_document(document_id)

    return PageExtractionResponse(
        document_id=document_id,
        page_count=len(pages),
        pages=[PageRead.model_validate(page) for page in pages],
    )


@router.get("/{document_id}/pages", response_model=list[PageRead])
async def list_document_pages(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> list[PageRead]:
    """List previously extracted pages for a document, in page order."""
    page_repository = PageRepository(session)
    pages = await page_repository.list_by_document(document_id)

    return [PageRead.model_validate(page) for page in pages]


@router.post(
    "/{document_id}/detect-structure",
    response_model=DocumentStructureResponse,
)
async def detect_document_structure(
    document_id: uuid.UUID,
    service: IngestionService = Depends(get_ingestion_service),
) -> DocumentStructureResponse:
    """
    Detect chapter/section structure for a document.

    Requires pages to already be extracted via POST /{document_id}/extract.
    Runs synchronously for now, same as extraction. Re-running this
    replaces any previously detected structure rather than duplicating it.
    """
    chapters = await service.detect_document_structure(document_id)

    return DocumentStructureResponse(
        document_id=document_id,
        chapters=[ChapterRead.model_validate(chapter) for chapter in chapters],
    )


@router.get("/{document_id}/structure", response_model=DocumentStructureResponse)
async def get_document_structure(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> DocumentStructureResponse:
    """Fetch previously detected structure for a document."""
    structure_repository = StructureRepository(session)
    chapters = await structure_repository.list_chapters_by_document(document_id)

    return DocumentStructureResponse(
        document_id=document_id,
        chapters=[ChapterRead.model_validate(chapter) for chapter in chapters],
    )


@router.post("/{document_id}/chunk", response_model=ChunkingResponse)
async def chunk_document(
    document_id: uuid.UUID,
    service: IngestionService = Depends(get_ingestion_service),
) -> ChunkingResponse:
    """
    Chunk a document's extracted pages into semantic chunks.

    Requires pages to already be extracted via POST /{document_id}/extract.
    Detecting structure first (POST /{document_id}/detect-structure) is
    optional but recommended — chunks created without it will have null
    chapter_id/section_id. Runs synchronously for now. Re-running this
    replaces any previously created chunks rather than duplicating them.
    """
    chunks = await service.chunk_document(document_id)

    return ChunkingResponse(
        document_id=document_id,
        chunk_count=len(chunks),
        chunks=[ChunkRead.model_validate(chunk) for chunk in chunks],
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
async def list_document_chunks(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_database_session),
) -> list[ChunkRead]:
    """List previously created chunks for a document, in document order."""
    chunk_repository = ChunkRepository(session)
    chunks = await chunk_repository.list_by_document(document_id)

    return [ChunkRead.model_validate(chunk) for chunk in chunks]
