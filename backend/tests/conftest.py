"""Shared pytest fixtures."""

from collections.abc import AsyncGenerator

import pytest
from app.main import create_application
from httpx import ASGITransport, AsyncClient
from tests.helpers import FakeRedis, install_auth_override


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client for API tests."""
    application = create_application()
    application.state.redis_client = FakeRedis()
    install_auth_override(application)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as test_client:
        test_client.app = application
        yield test_client
