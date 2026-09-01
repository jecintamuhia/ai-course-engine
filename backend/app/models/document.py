"""Document model: uploaded source material (textbooks, etc.)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DocumentStatus(str, enum.Enum):
    """Lifecycle status of a document record."""

    UPLOADED = "uploaded"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    An uploaded source document (e.g. a textbook) and its storage metadata.

    Documents are versioned via a self-referential chain: uploading a new
    version of previously ingested material creates a new row linked to
    its predecessor via ``previous_version_id``, rather than mutating the
    original record. Only one version per lineage is ``is_latest_version``
    at a time.
    """

    __tablename__ = "documents"

    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    storage_filename: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    sha256_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )

    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    is_latest_version: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )

    previous_version: Mapped["Document | None"] = relationship(
        "Document",
        remote_side="Document.id",
        foreign_keys=[previous_version_id],
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Document id={self.id} filename={self.original_filename!r} "
            f"version={self.version_number} latest={self.is_latest_version}>"
        )