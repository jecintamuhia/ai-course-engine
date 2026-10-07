"""CLI demo: generate, review, and publish course content for one week.

Runs against the configured database and AI provider directly through the
application services (no HTTP server required).

Usage (from the backend directory, with the venv active):

    $env:DATABASE_URL="postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine"
    python scripts/demo_course_content.py [--curriculum <uuid>] [--week 1]

The DATABASE_URL override points the host at the Docker-published Postgres
(backend/.env uses the docker-internal ``postgres`` hostname). The script
skips Moodle publish cleanly when the instance is unreachable.

Flow:

    1. Pick the latest APPROVED/PUBLISHED curriculum (or the one given by
       ``--curriculum``) and the weekly unit given by ``--week``.
    2. Generate lecturer-reviewable lessons for that week using the LLM.
    3. Submit the first generated lesson and approve it.
    4. Publish the curriculum to Moodle (when MOODLE_URL/MOODLE_TOKEN are
       configured), attaching the APPROVED lesson as a lesson page.

The script never deletes or fabricates data: generation preserves any
already-approved lessons and only adds lesson pages that are missing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Allow direct `python scripts/demo_course_content.py` execution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.db.database import create_database_engine  # noqa: E402
from app.db.repositories.chunks import ChunkRepository  # noqa: E402
from app.db.repositories.courses import CourseRepository  # noqa: E402
from app.db.repositories.curriculum import CurriculumRepository  # noqa: E402
from app.db.repositories.lessons import LessonRepository  # noqa: E402
from app.models.curriculum import Curriculum, CurriculumStatus  # noqa: E402
from app.models.curriculum_unit import CurriculumUnit  # noqa: E402
from app.services.ai.factory import create_llm_provider  # noqa: E402
from app.services.course_content.service import CourseContentService  # noqa: E402
from app.services.moodle.client import create_moodle_client  # noqa: E402
from app.services.moodle.lessons import build_lesson_renderer  # noqa: E402
from app.services.moodle.sync import MoodleSyncService  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402


async def _pick_curriculum(
    session: AsyncSession,
    curriculum_id: uuid.UUID | None,
) -> Curriculum | None:
    if curriculum_id is not None:
        result = await session.execute(
            select(Curriculum).where(Curriculum.id == curriculum_id)
        )
        return result.scalar_one_or_none()

    result = await session.execute(
        select(Curriculum)
        .where(
            Curriculum.status.in_(
                (CurriculumStatus.APPROVED, CurriculumStatus.PUBLISHED)
            )
        )
        .order_by(Curriculum.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _pick_unit(
    session: AsyncSession,
    curriculum: Curriculum,
    week_number: int,
) -> CurriculumUnit | None:
    result = await session.execute(
        select(CurriculumUnit)
        .where(
            CurriculumUnit.curriculum_id == curriculum.id,
            CurriculumUnit.week_number == week_number,
        )
        .order_by(CurriculumUnit.order_index)
    )
    return result.scalars().first()


async def run(*, curriculum_id: uuid.UUID | None, week: int) -> int:
    settings = Settings()
    engine = create_database_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        curriculum = await _pick_curriculum(session, curriculum_id)
        if curriculum is None:
            print("No APPROVED/PUBLISHED curriculum found. Generate and review "
                  "a curriculum first.")
            return 1

        unit = await _pick_unit(session, curriculum, week)
        if unit is None:
            print(f"Curriculum {curriculum.id} has no week {week}.")
            return 1

        curriculum_repository = CurriculumRepository(session)
        lesson_repository = LessonRepository(session)
        service = CourseContentService(
            curriculum_repository,
            ChunkRepository(session),
            lesson_repository,
            create_llm_provider(settings),
            settings=settings,
        )

        print(f"Generating lessons for week {week} of curriculum "
              f"{curriculum.title!r} ({curriculum.id})")
        result = await service.generate_week(unit.id)
        generated = result["generated"]
        print(f"  generated={len(generated)} skipped="
              f"{len(result['skipped'])} errors={len(result['errors'])}")
        for lesson in generated:
            print(f"  - [{lesson.status.value}] {lesson.title}")

        pre_approved = await lesson_repository.list_publishable_by_curriculum(
            curriculum.id
        )
        print(f"APPROVED lessons before review: {len(pre_approved)}")

        if generated:
            lesson = generated[0]
            print(f"Approving '{lesson.title}' "
                  f"(status={lesson.status.value}).")
            await service.review_lesson(
                lesson.id,
                decision="approved",
                reviewer_name="CLI demo",
                comments="Auto-approved by demo script.",
            )

        approved = await lesson_repository.list_publishable_by_curriculum(
            curriculum.id
        )
        await lesson_repository.commit()
        print(f"APPROVED lessons after review: {len(approved)}")

        client = create_moodle_client(settings)
        if client is None:
            print("MOODLE_URL/MOODLE_TOKEN not set — skipping Moodle publish.")
            return 0

        try:
            await client.get_site_info()
        except Exception as exc:
            print(f"Moodle unreachable ({type(exc).__name__}) — skipping "
                  "publish. Re-run this script after connectivity returns.")
            return 0

        sync_service = MoodleSyncService(
            client,
            curriculum_repository,
            CourseRepository(session),
            moodle_base_url=settings.moodle_url,
            moodle_course_category_id=settings.moodle_course_category_id,
        )
        print("Publishing curriculum to Moodle…")
        published = await sync_service.publish_curriculum(
            curriculum.id,
            lesson_renderer=build_lesson_renderer(approved),
        )
        print(f"Published moodle_course_id={published.moodle_course_id} "
              f"created={published.created} verified={published.verified} "
              f"lessons_in_plan={len(approved)}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum", type=uuid.UUID, default=None)
    parser.add_argument("--week", type=int, default=1)
    args = parser.parse_args()
    try:
        return asyncio.run(run(curriculum_id=args.curriculum, week=args.week))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
