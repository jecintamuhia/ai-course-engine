"""Unit tests for DocumentStorageService using an in-memory fake repository."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.exceptions import DocumentNotFound, DocumentProcessingError
from app.models.document import Document
from app.services.document_storage import DocumentStorageService


class FakeUploadFile:
    """Minimal stand-in for FastAPI's UploadFile in unit tests."""

    def __init__(self, filename: str, content: bytes, content_type: str) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._content[self._offset :]
            self._offset = len(self._content)
            return chunk

        chunk = self._content[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class FakeDocumentRepository:
    """In-memory stand-in for DocumentRepository in unit tests."""

    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, Document] = {}
        self.added: list[Document] = []
        self.committed = False

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.documents.get(document_id)

    async def get_latest_by_hash(self, sha256_hash: str) -> Document | None:
        for document in self.documents.values():
            if document.sha256_hash == sha256_hash and document.is_latest_version:
                return document
        return None

    async def add(self, document: Document) -> Document:
        document.id = document.id or uuid.uuid4()
        self.documents[document.id] = document
        self.added.append(document)
        return document

    async def mark_superseded(self, document: Document) -> None:
        document.is_latest_version = False

    async def commit(self) -> None:
        self.committed = True


PDF_BYTES = b"%PDF-1.7 minimal valid-looking pdf content for tests"


def make_settings(upload_dir: Path) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://u:p@localhost:5432/db",
        upload_dir=str(upload_dir),
        max_upload_size_mb=1,
    )


@pytest.mark.asyncio
async def test_store_upload_persists_new_document(tmp_path: Path) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    upload = FakeUploadFile("textbook.pdf", PDF_BYTES, "application/pdf")

    document, is_duplicate = await service.store_upload(upload)

    assert is_duplicate is False
    assert document.version_number == 1
    assert document.is_latest_version is True
    assert await asyncio.to_thread(Path(document.storage_path).exists)
    assert await asyncio.to_thread(Path(document.storage_path).read_bytes) == PDF_BYTES
    assert repository.committed is True


@pytest.mark.asyncio
async def test_store_upload_detects_duplicate_content(
    tmp_path: Path,
) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    first_upload = FakeUploadFile("textbook.pdf", PDF_BYTES, "application/pdf")
    first_document, _ = await service.store_upload(first_upload)

    second_upload = FakeUploadFile("copy.pdf", PDF_BYTES, "application/pdf")
    second_document, is_duplicate = await service.store_upload(second_upload)

    assert is_duplicate is True
    assert second_document.id == first_document.id


@pytest.mark.asyncio
async def test_store_upload_creates_new_version_when_replacing(
    tmp_path: Path,
) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    original_upload = FakeUploadFile("v1.pdf", PDF_BYTES, "application/pdf")
    original, _ = await service.store_upload(original_upload)

    new_content = PDF_BYTES + b" updated edition"
    new_upload = FakeUploadFile("v2.pdf", new_content, "application/pdf")

    new_document, is_duplicate = await service.store_upload(
        new_upload, replaces_document_id=original.id
    )

    assert is_duplicate is False
    assert new_document.version_number == 2
    assert new_document.previous_version_id == original.id
    assert original.is_latest_version is False


@pytest.mark.asyncio
async def test_store_upload_rejects_oversized_file(tmp_path: Path) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    oversized_content = b"%PDF-1.7 " + (b"a" * (2 * 1024 * 1024))
    upload = FakeUploadFile("big.pdf", oversized_content, "application/pdf")

    with pytest.raises(DocumentProcessingError):
        await service.store_upload(upload)


@pytest.mark.asyncio
async def test_store_upload_rejects_unsupported_extension(
    tmp_path: Path,
) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    upload = FakeUploadFile("script.exe", b"MZ...", "application/octet-stream")

    with pytest.raises(DocumentProcessingError):
        await service.store_upload(upload)


@pytest.mark.asyncio
async def test_store_upload_replace_missing_document_raises(
    tmp_path: Path,
) -> None:
    repository = FakeDocumentRepository()
    settings = make_settings(tmp_path)
    service = DocumentStorageService(repository, settings)

    upload = FakeUploadFile("v2.pdf", PDF_BYTES, "application/pdf")

    with pytest.raises(DocumentNotFound):
        await service.store_upload(upload, replaces_document_id=uuid.uuid4())
