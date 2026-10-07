"""API-level tests for course-content routes (dependency overridden)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.api.v1.course_content import get_course_content_service
from app.main import create_application
from app.models.lesson import Lesson, LessonStatus
from app.models.lesson_content_block import (
    BlockReviewStatus,
    LessonBlockType,
    LessonContentBlock,
)
from httpx import ASGITransport, AsyncClient
from tests.helpers import install_auth_override


class _FakeCourseContentService:
    def __init__(self) -> None:
        self.unit_id = uuid.uuid4()
        self.lesson = self._lesson()

    def _lesson(self) -> Lesson:
        lesson = Lesson(
            id=uuid.uuid4(),
            curriculum_id=uuid.uuid4(),
            curriculum_unit_id=self.unit_id,
            week_number=1,
            order_index=0,
            title="Alpha Lesson",
            description="About Alpha.",
            learning_objectives=["Explain Alpha."],
            estimated_workload_minutes=40,
            status=LessonStatus.AWAITING_REVIEW,
            generation_errors=[],
        )
        lesson.created_at = datetime.now(UTC)
        lesson.updated_at = datetime.now(UTC)
        block = LessonContentBlock(
            id=uuid.uuid4(),
            lesson_id=lesson.id,
            block_type=LessonBlockType.TEXT,
            order_index=0,
            title=None,
            payload={"content": "Alpha is fundamental.", "source_chunk_markers": []},
            review_status=BlockReviewStatus.APPROVED,
        )
        block.created_at = datetime.now(UTC)
        block.updated_at = datetime.now(UTC)
        lesson.content_blocks = [block]
        return lesson

    async def get_lesson(self, lesson_id: uuid.UUID) -> Lesson:
        return self.lesson

    async def list_lessons(self, curriculum_unit_id: uuid.UUID) -> list[Lesson]:
        return [self.lesson]

    async def generate_week(self, curriculum_unit_id: uuid.UUID) -> dict:
        return {
            "generated": [self.lesson],
            "skipped": [],
            "errors": [],
        }

    async def submit_for_review(self, lesson_id: uuid.UUID) -> Lesson:
        return self.lesson

    async def review_lesson(self, lesson_id, **kwargs) -> Lesson:
        return self.lesson

    async def review_block(self, block_id, **kwargs) -> LessonContentBlock:
        return self.lesson.content_blocks[0]

    async def get_source_map(self, lesson_id: uuid.UUID):
        from app.schemas.course_content import LessonSourceMapRead

        return LessonSourceMapRead(lesson_id=lesson_id, sources=[])


def _build_client(_fake):
    application = create_application()
    install_auth_override(application)
    application.dependency_overrides[get_course_content_service] = lambda: _fake
    return application


async def test_get_lesson_round_trips_schema() -> None:
    fake = _FakeCourseContentService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(f"/api/v1/course-content/lessons/{fake.lesson.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Alpha Lesson"
    assert body["status"] == "awaiting_review"
    assert body["blocks"][0]["block_type"] == "text"


async def test_list_lessons_for_week() -> None:
    fake = _FakeCourseContentService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/course-content/weeks/{fake.unit_id}/lessons"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["curriculum_unit_id"] == str(fake.unit_id)
    assert len(body["lessons"]) == 1


async def test_generate_week_endpoint() -> None:
    fake = _FakeCourseContentService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/api/v1/course-content/weeks/{fake.unit_id}/generate"
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["generated"]) == 1
    assert body["generated"][0]["title"] == "Alpha Lesson"


async def test_review_endpoint_returns_lesson() -> None:
    fake = _FakeCourseContentService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            f"/api/v1/course-content/lessons/{fake.lesson.id}/review",
            json={"decision": "approved", "reviewer_name": "Dr. Test"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_review"


async def test_source_map_endpoint() -> None:
    fake = _FakeCourseContentService()
    application = _build_client(fake)

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/course-content/lessons/{fake.lesson.id}/source-map"
        )

    assert response.status_code == 200
    assert response.json()["sources"] == []
