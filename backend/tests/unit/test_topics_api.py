"""Route-level tests for document analysis warnings."""

from __future__ import annotations

import uuid

import pytest
from app.api.v1.topics import get_content_analysis_service
from app.main import create_application
from app.models.user import UserRole
from app.schemas.topic import AnalysisWarningRead
from httpx import ASGITransport, AsyncClient
from tests.helpers import FakeRedis, install_auth_override

DOCUMENT_ID = uuid.uuid4()


class FakeContentAnalysisService:
    async def analyze_document_with_report(self, document_id):
        return [], [
            AnalysisWarningRead(
                kind="context_truncated",
                message="Later source chunks were omitted.",
                chapter_id=uuid.uuid4(),
                chapter_title="Chapter 1",
                omitted_chunks=2,
                total_chunks=5,
                max_chars=6000,
            )
        ]


@pytest.mark.asyncio
async def test_analyze_response_includes_extraction_warnings() -> None:
    application = create_application()
    application.state.redis_client = FakeRedis()
    install_auth_override(application, role=UserRole.LECTURER)
    application.dependency_overrides[get_content_analysis_service] = (
        lambda: FakeContentAnalysisService()
    )

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.post(f"/api/v1/documents/{DOCUMENT_ID}/analyze")

    assert response.status_code == 200
    body = response.json()
    assert body["topic_count"] == 0
    assert body["warnings"][0]["kind"] == "context_truncated"
    assert body["warnings"][0]["omitted_chunks"] == 2
    assert body["warnings"][0]["total_chunks"] == 5
