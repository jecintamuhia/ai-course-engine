"""Course model: tracks a curriculum's published state in Moodle."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class CourseStatus(str, enum.Enum):
    """Publication status of a course in Moodle."""

    SYNCED = "synced"
    SYNC_FAILED = "sync_failed"


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A course published to Moodle from a generated curriculum.

    ``idnumber`` is the Moodle course idnumber used for idempotent
    find-or-create: publishing the same curriculum twice reuses the
    existing Moodle course instead of creating duplicates.
    """

    __tablename__ = "courses"

    curriculum_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("curricula.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    fullname: Mapped[str] = mapped_column(String(500), nullable=False)
    shortname: Mapped[str] = mapped_column(String(255), nullable=False)
    idnumber: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    moodle_course_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    moodle_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    status: Mapped[CourseStatus] = mapped_column(
        Enum(
            CourseStatus,
            name="course_status",
            native_enum=True,
            validate_strings=True,
        ),
        nullable=False,
        default=CourseStatus.SYNCED,
    )

    sections_published: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resources_published: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Course id={self.id} idnumber={self.idnumber!r} "
            f"moodle_course_id={self.moodle_course_id} status={self.status}>"
        )
