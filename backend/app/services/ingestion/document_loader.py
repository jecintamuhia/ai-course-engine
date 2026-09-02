"""Loads stored document content from disk for extraction."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.exceptions import DocumentProcessingError
from app.models.document import Document


async def load_document_content(document: Document) -> bytes:
    """
    Read a document's stored file content from disk.

    Raises DocumentProcessingError if the file is missing or unreadable,
    which can happen if storage was modified out-of-band from the
    database record.
    """
    path = Path(document.storage_path)

    def _read() -> bytes:
        if not path.is_file():
            raise DocumentProcessingError(
                f"Stored file for document {document.id} was not found "
                f"on disk."
            )
        return path.read_bytes()

    return await asyncio.to_thread(_read)