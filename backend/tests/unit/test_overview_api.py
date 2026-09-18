"""Route-level tests for the dashboard and document overview endpoints.

Exercises /api/v1/dashboard and /api/v1/documents without a database by
overriding the overview-service dependency with a mock.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from app.api.v1.overview import get_overview_service
from app.main import app
from app.models.document import Document, DocumentStatus

DASHBOARD_URL = "/api/v1/dashboard"
DOCUMENTS_URL = "/api/v1/documents"


def _make_document():
    doc = Document(
        original_filename="textbook.pdf",
        storage_filename="storage.pdf",
        storage_path="/tmp/storage.pdf",
        mime_type="application/pdf",
        file_extension=".pdf",
        size_bytes=123456,
        sha256_hash="a" * 64,
        version_number=1,
        is_latest_version=True,
        status=DocumentStatus.UPLOADED,
    )
    doc.id = uuid.uuid4()
    doc.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    doc.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
    return doc


def _overview(document):
    return {
        "document": document,
        "page_count": 9,
        "chapter_count": 8,
        "chunk_count": 13,
        "topic_count": 5,
        "curriculum_count": 1,
        "latest_job": None,
    }


async def _client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.pop(get_overview_service, None)
    app.state.moodle_client = None
    yield
    app.dependency_overrides.pop(get_overview_service, None)
    app.state.moodle_client = None


@pytest.mark.anyio
async def test_dashboard_endpoint_returns_aggregates() -> None:
    service = AsyncMock()
    service.dashboard.return_value = {
        "documents_total": 2,
        "documents_processing": 1,
        "curricula_total": 3,
        "curricula_pending_review": 1,
        "curricula_approved": 1,
        "curricula_published": 0,
        "courses_published": 0,
        "moodle": {"configured": False, "moodle_url": None, "connected": False},
    }
    app.dependency_overrides[get_overview_service] = lambda: service

    async with await _client() as client:
        response = await client.get(DASHBOARD_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents_total"] == 2
    assert payload["documents_processing"] == 1
    assert payload["curricula_pending_review"] == 1
    assert payload["curricula_approved"] == 1
    assert payload["courses_published"] == 0
    assert payload["moodle"]["configured"] is False

    call_kwargs = service.dashboard.await_args.kwargs
    assert call_kwargs["moodle_status"]["configured"] is False


@pytest.mark.anyio
async def test_dashboard_never_fails_without_moodle() -> None:
    service = AsyncMock()
    service.dashboard.return_value = {
        "documents_total": 0,
        "documents_processing": 0,
        "curricula_total": 0,
        "curricula_pending_review": 0,
        "curricula_approved": 0,
        "curricula_published": 0,
        "courses_published": 0,
        "moodle": None,
    }
    app.dependency_overrides[get_overview_service] = lambda: service

    async with await _client() as client:
        response = await client.get(DASHBOARD_URL)

    assert response.status_code == 200
    assert response.json()["moodle"] is None


@pytest.mark.anyio
async def test_documents_endpoint_lists_documents() -> None:
    document = _make_document()
    service = AsyncMock()
    service.list_overviews.return_value = [_overview(document)]
    app.dependency_overrides[get_overview_service] = lambda: service

    async with await _client() as client:
        response = await client.get(DOCUMENTS_URL)

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["documents"]) == 1
    entry = payload["documents"][0]
    assert entry["document"]["original_filename"] == "textbook.pdf"
    assert entry["document"]["id"] == str(document.id)
    assert entry["page_count"] == 9
    assert entry["topic_count"] == 5
    assert entry["curriculum_count"] == 1
    assert entry["latest_job"] is None


@pytest.mark.anyio
async def test_document_overview_endpoint_returns_single() -> None:
    document = _make_document()
    service = AsyncMock()
    service.list_overviews.return_value = [_overview(document)]
    app.dependency_overrides[get_overview_service] = lambda: service

    async with await _client() as client:
        response = await client.get(f"{DOCUMENTS_URL}/{document.id}/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["document"]["original_filename"] == "textbook.pdf"
    assert payload["chapter_count"] == 8
    assert payload["chunk_count"] == 13


@pytest.mark.anyio
async def test_document_overview_returns_404_for_unknown_id() -> None:
    service = AsyncMock()
    service.list_overviews.return_value = []
    app.dependency_overrides[get_overview_service] = lambda: service

    async with await _client() as client:
        response = await client.get(f"{DOCUMENTS_URL}/{uuid.uuid4()}/overview")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"