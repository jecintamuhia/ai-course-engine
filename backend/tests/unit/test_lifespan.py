"""Unit tests for application lifespan resource wiring."""

from __future__ import annotations

from unittest.mock import Mock

from app.main import create_application, lifespan
from app.services.ai.base import LLMProvider


async def test_lifespan_attaches_llm_provider(monkeypatch) -> None:
    mock_provider = Mock(spec=LLMProvider)

    monkeypatch.setattr(
        "app.main.create_llm_provider",
        lambda settings: mock_provider,
    )

    application = create_application()

    async with lifespan(application):
        assert application.state.llm_provider is mock_provider