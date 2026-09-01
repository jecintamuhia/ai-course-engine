"""Unit tests for document file-validation utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.utils.files import (
    FileValidationError,
    compute_sha256,
    generate_storage_filename,
    resolve_safe_storage_path,
    sanitize_display_filename,
    sniff_extension,
    validate_declared_mime_type,
    validate_extension,
    validate_file_content,
    validate_file_size,
)


def test_validate_extension_accepts_pdf() -> None:
    assert validate_extension("textbook.pdf") == ".pdf"


def test_validate_extension_accepts_docx() -> None:
    assert validate_extension("notes.DOCX") == ".docx"


def test_validate_extension_rejects_unsupported() -> None:
    with pytest.raises(FileValidationError):
        validate_extension("payload.exe")


def test_validate_declared_mime_type_matches() -> None:
    validate_declared_mime_type("application/pdf", ".pdf")


def test_validate_declared_mime_type_mismatch_raises() -> None:
    with pytest.raises(FileValidationError):
        validate_declared_mime_type("text/plain", ".pdf")


def test_sniff_extension_detects_pdf_signature() -> None:
    content = b"%PDF-1.7 rest of file"
    assert sniff_extension(content) == ".pdf"


def test_sniff_extension_detects_docx_signature() -> None:
    content = b"PK\x03\x04 rest of zip"
    assert sniff_extension(content) == ".docx"


def test_sniff_extension_returns_none_for_unknown_content() -> None:
    assert sniff_extension(b"plain text content") is None


def test_validate_file_content_mismatch_raises() -> None:
    content = b"PK\x03\x04 zip signature"
    with pytest.raises(FileValidationError):
        validate_file_content(content, ".pdf")


def test_validate_file_content_matches() -> None:
    content = b"%PDF-1.7 minimal"
    validate_file_content(content, ".pdf")


def test_validate_file_size_rejects_empty() -> None:
    with pytest.raises(FileValidationError):
        validate_file_size(0, 1000)


def test_validate_file_size_rejects_oversized() -> None:
    with pytest.raises(FileValidationError):
        validate_file_size(2000, 1000)


def test_validate_file_size_accepts_within_limit() -> None:
    validate_file_size(500, 1000)


def test_sanitize_display_filename_strips_directory_components() -> None:
    assert sanitize_display_filename("../../etc/passwd") == "passwd"


def test_sanitize_display_filename_replaces_unsafe_characters() -> None:
    result = sanitize_display_filename("my textbook!@#.pdf")
    assert result == "my_textbook_.pdf"


def test_generate_storage_filename_is_unique() -> None:
    first = generate_storage_filename(".pdf")
    second = generate_storage_filename(".pdf")
    assert first != second
    assert first.endswith(".pdf")


def test_compute_sha256_is_deterministic() -> None:
    content = b"identical content"
    assert compute_sha256(content) == compute_sha256(content)


def test_compute_sha256_differs_for_different_content() -> None:
    assert compute_sha256(b"a") != compute_sha256(b"b")


def test_resolve_safe_storage_path_stays_within_root(tmp_path: Path) -> None:
    resolved = resolve_safe_storage_path(tmp_path, "abc123.pdf")
    assert resolved.parent == tmp_path.resolve()


def test_resolve_safe_storage_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(FileValidationError):
        resolve_safe_storage_path(tmp_path, "../escape.pdf")