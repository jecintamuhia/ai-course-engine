import uuid
from unittest.mock import AsyncMock

import pytest
from app.models.content_generation_job import ContentGenerationJob
from app.models.curriculum import CurriculumStatus
from app.services.course_content.generation_jobs import ContentGenerationService


@pytest.mark.anyio
async def test_regeneration_of_published_curriculum_reopens_review_cycle() -> None:
    curriculum_id = uuid.uuid4()
    curriculum = type(
        "CurriculumStub",
        (),
        {
            "id": curriculum_id,
            "status": CurriculumStatus.PUBLISHED,
            "units": [object() for _ in range(16)],
        },
    )()
    curriculum_repository = AsyncMock()
    curriculum_repository.get_by_id.return_value = curriculum
    job_repository = AsyncMock()
    job_repository.get_active_for_curriculum.return_value = None

    async def add_job(job: ContentGenerationJob) -> None:
        job.id = uuid.uuid4()

    job_repository.add.side_effect = add_job
    redis_client = AsyncMock()
    service = ContentGenerationService(
        curriculum_repository, job_repository, redis_client
    )

    job, created = await service.start(curriculum_id)

    assert created is True
    assert job.curriculum_id == curriculum_id
    assert job.total_weeks == 16
    assert curriculum.status == CurriculumStatus.APPROVED
    job_repository.commit.assert_awaited_once()
    redis_client.lpush.assert_awaited_once()
