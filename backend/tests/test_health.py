"""Health endpoint tests."""

from httpx import AsyncClient


async def test_health_endpoint(
    client: AsyncClient,
) -> None:
    """The liveness endpoint should return HTTP 200."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_returns_request_id(
    client: AsyncClient,
) -> None:
    """Responses should include a request correlation ID."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")