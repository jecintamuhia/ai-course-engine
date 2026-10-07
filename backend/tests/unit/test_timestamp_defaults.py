"""Regression tests for client-side timestamp defaults.

Server-side ``default=func.now()`` / ``onupdate=func.now()`` leave a
column unloaded after flush, so reading it after commit triggers a lazy
refresh that raises ``MissingGreenlet`` in async contexts. Columns used
in post-commit responses must carry a client-side default/onupdate.
"""

from collections.abc import Callable

from app.db.base import TimestampMixin
from app.models.curriculum_review import CurriculumReview
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _client_default(column) -> Callable | None:
    """Return the client-side default callable, if one is configured."""
    if column.default is None:
        return None
    if not callable(column.default.arg):
        return None
    return column.default.arg


def _client_onupdate(column) -> Callable | None:
    """Return the client-side onupdate callable, if one is configured."""
    if column.onupdate is None:
        return None
    if not callable(column.onupdate.arg):
        return None
    return column.onupdate.arg


class _MixinHarness(DeclarativeBase):
    pass


class _Timestamped(_MixinHarness, TimestampMixin):
    __tablename__ = "zz_test_timestamped"

    id: Mapped[int] = mapped_column(primary_key=True)


class TestTimestampMixin:
    def test_created_at_has_client_default(self) -> None:
        column = _Timestamped.__table__.c.created_at
        assert _client_default(column) is not None

    def test_updated_at_has_client_default_and_onupdate(self) -> None:
        column = _Timestamped.__table__.c.updated_at
        assert _client_default(column) is not None
        assert _client_onupdate(column) is not None


class TestReviewedAtClientDefault:
    def test_reviewed_at_has_client_default(self) -> None:
        column = CurriculumReview.__table__.c.reviewed_at
        assert _client_default(column) is not None
