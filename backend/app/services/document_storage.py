"""Document storage service: validation, hashing, and persistence for uploads."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.exceptions import DocumentNotFound, DocumentProcessingError
from app.db.repositories.documents import DocumentRepository
from app.models.document import Document
from app.utils.files import (
    FileValidationError,
    compute_sha256,
    generate_storage_filename,
    resolve_safe_storage_path,
    sanitize_display_filename,
    validate_declared_mime_type,
    validate_extension,
    validate_file_content,
    validate_file_size,
)


class DocumentStorageService:
    """Coordinates validation, hashing, on-disk storage, and persistence."""

    def __init__(
        self,
        repository: DocumentRepository,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._upload_root = Path(settings.upload_dir)

    async def store_upload(
        self,
        file: UploadFile,
        *,
        replaces_document_id: uuid.UUID | None = None,
    ) -> tuple[Document, bool]:
        """
        Validate, hash, and persist an uploaded document.

        Returns a tuple of (document, is_duplicate). If content identical to
        an existing latest-version document is uploaded, no new file is
        written to disk and the existing document is returned with
        is_duplicate=True, unless replaces_document_id is provided, in
        which case a new version is always created.
        """
        if not file.filename:
            raise DocumentProcessingError("Uploaded file has no filename.")

        try:
            extension = validate_extension(file.filename)
            validate_declared_mime_type(file.content_type, extension)
        except FileValidationError as exc:
            raise DocumentProcessingError(str(exc)) from exc

        content = await self._read_within_limit(file)

        try:
            validate_file_size(
                len(content), self._settings.max_upload_size_bytes
            )
            validate_file_content(content, extension)
        except FileValidationError as exc:
            raise DocumentProcessingError(str(exc)) from exc

        sha256_hash = compute_sha256(content)

        previous_version: Document | None = None

        if replaces_document_id is not None:
            previous_version = await self._repository.get_by_id(
                replaces_document_id
            )

            if (
                previous_version is None
                or not previous_version.is_latest_version
            ):
                raise DocumentNotFound(
                    "The document to be replaced does not exist or is "
                    "not the latest version."
                )
        else:
            existing = await self._repository.get_latest_by_hash(
                sha256_hash
            )

            if existing is not None:
                return existing, True

        try:
            display_filename = sanitize_display_filename(file.filename)
        except FileValidationError as exc:
            raise DocumentProcessingError(str(exc)) from exc

        storage_filename = generate_storage_filename(extension)

        try:
            storage_path = resolve_safe_storage_path(
                self._upload_root, storage_filename
            )
        except FileValidationError as exc:
            raise DocumentProcessingError(str(exc)) from exc

        await self._write_file(storage_path, content)

        document = Document(
            original_filename=display_filename,
            storage_filename=storage_filename,
            storage_path=str(storage_path),
            mime_type=file.content_type or "",
            file_extension=extension,
            size_bytes=len(content),
            sha256_hash=sha256_hash,
            version_number=(
                previous_version.version_number + 1
                if previous_version
                else 1
            ),
            previous_version_id=(
                previous_version.id if previous_version else None
            ),
            is_latest_version=True,
        )

        if previous_version is not None:
            await self._repository.mark_superseded(previous_version)

        await self._repository.add(document)
        await self._repository.commit()

        return document, False

    async def _read_within_limit(self, file: UploadFile) -> bytes:
        """
        Read an uploaded file's content, aborting early if it exceeds the
        configured size limit, without loading unbounded data into memory.
        """
        max_bytes = self._settings.max_upload_size_bytes
        chunk_size = 1024 * 1024

        chunks: list[bytes] = []
        total = 0

        while True:
            chunk = await file.read(chunk_size)

            if not chunk:
                break

            total += len(chunk)

            if total > max_bytes:
                raise DocumentProcessingError(
                    f"File exceeds the maximum allowed size of "
                    f"{max_bytes} bytes."
                )

            chunks.append(chunk)

        return b"".join(chunks)

    async def _write_file(self, path: Path, content: bytes) -> None:
        """Write file content to disk without blocking the event loop."""

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(_write)