"""Tests for the async database session factory configuration."""

from unittest.mock import Mock

from app.db.session import create_session_factory


class TestCreateSessionFactory:
    """Factory options must prevent async lazy loads after commit."""

    def test_expire_on_commit_is_disabled(self) -> None:
        factory = create_session_factory(Mock())
        assert factory.kw["expire_on_commit"] is False

    def test_autoflush_is_disabled(self) -> None:
        factory = create_session_factory(Mock())
        assert factory.kw["autoflush"] is False
