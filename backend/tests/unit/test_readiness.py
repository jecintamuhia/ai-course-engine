"""Readiness endpoint tests.

The readiness probe is what Railway uses to decide whether a deployment is
allowed to receive traffic. It must execute a real SQLAlchemy statement
(not a raw string) and report dependency failures as 503 instead of
crashing.
"""

from __future__ import annotations

from app.main import create_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy import TextClause


class _FakeConnection:
    async def execute(self, statement: object) -> None:
        assert isinstance(statement, TextClause), (
            "readiness must execute a SQLAlchemy text() clause"
        )


class _FakeBegin:
    async def __aenter__(self) -> _FakeConnection:
        return _FakeConnection()

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


class _FakeEngine:
    def begin(self) -> _FakeBegin:
        return _FakeBegin()


class _FailingEngine:
    def begin(self) -> _FakeBegin:
        raise RuntimeError("database unreachable")


class _FakeRedis:
    async def ping(self) -> bool:
        return True


class _FailingRedis:
    async def ping(self) -> bool:
        raise RuntimeError("redis unreachable")


async def _get(path: str, app) -> object:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def test_readiness_executes_text_clause_and_returns_ready() -> None:
    app = create_application()
    app.state.engine = _FakeEngine()
    app.state.redis_client = _FakeRedis()

    response = await _get("/health/ready", app)

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_reports_database_failure_as_503() -> None:
    app = create_application()
    app.state.engine = _FailingEngine()
    app.state.redis_client = _FakeRedis()

    response = await _get("/health/ready", app)

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unreachable",
    }


async def test_readiness_reports_redis_failure_as_503() -> None:
    app = create_application()
    app.state.engine = _FakeEngine()
    app.state.redis_client = _FailingRedis()

    response = await _get("/health/ready", app)

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ok",
        "redis": "unreachable",
    }
