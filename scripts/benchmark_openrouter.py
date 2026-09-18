"""Benchmark OpenRouter candidate models on a real textbook chapter.

Mimics the production analysis path: real chapters/chunks from the
database, the real extraction prompt, and the same per-chapter context
bound. For each candidate model it measures end-to-end latency, API
attempts (transport retries + schema-correction retries), token usage,
and estimated USD cost, and it validates the extracted structure.

Models default to the production candidates:
  anthropic/claude-sonnet-4.5
  google/gemini-3.1-pro-preview
  openai/gpt-5.4

Overrides: OPENROUTER_BENCHMARK_MODELS="model-a,model-b,..."
          OPENROUTER_BENCHMARK_DOC_ID=<uuid of the document>
          OPENROUTER_BENCHMARK_OUTPUT=<path to results json>
          OPENROUTER_BENCHMARK_TEST_MODE=1  (offline latin input, no API)

Run from the repo root with the project venv:
  .venv\\Scripts\\python scripts\\benchmark_openrouter.py

The API key is read from backend/.env (settings) and is never printed.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.db.database import create_database_engine  # noqa: E402
from app.db.session import create_session_factory  # noqa: E402
from app.models.chapter import Chapter  # noqa: E402
from app.models.chunks import Chunk  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.schemas.ai_extraction import TopicExtractionResult  # noqa: E402
from app.services.ai.openrouter_provider import OpenRouterProvider  # noqa: E402
from app.services.ai.prompts import (  # noqa: E402
    TOPIC_EXTRACTION_SYSTEM_PROMPT,
    build_topic_extraction_user_prompt,
)
from app.services.content_analysis import chunk_context  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

DEFAULT_MODELS = [
    "anthropic/claude-sonnet-4.5",
    "google/gemini-3.1-pro-preview",
    "openai/gpt-5.4",
]

# Per-token pricing from OpenRouter /api/v1/models (verified 2026-09-17).
PRICING_PER_TOKEN = {
    "anthropic/claude-sonnet-4.5": (0.000003, 0.000015),
    "google/gemini-3.1-pro-preview": (0.000002, 0.000012),
    "openai/gpt-5.4": (0.0000025, 0.000015),
}


class _CountingProvider(OpenRouterProvider):
    """OpenRouterProvider that counts every HTTP POST for retry metrics."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.post_count = 0

    async def _send(self, *args, **kwargs) -> dict:
        self.post_count += 1
        return await super()._send(*args, **kwargs)


async def _load_benchmark_chapter(settings) -> tuple[object, list[Chunk], str]:
    doc_id = os.environ.get(
        "OPENROUTER_BENCHMARK_DOC_ID",
        "5c025566-fe88-43c5-a221-19af0ef09282",
    )
    engine = create_database_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            doc = await session.scalar(
                select(Document).where(Document.id == doc_id)
            )
            if doc is None:
                raise SystemExit(f"document {doc_id} not found")

            chapter_rows = await session.execute(
                select(Chapter, func.count(Chunk.id))
                .outerjoin(Chunk, Chunk.chapter_id == Chapter.id)
                .where(Chapter.document_id == doc.id)
                .group_by(Chapter.id)
                .order_by(Chapter.order_index)
            )
            best = None
            best_count = 0
            for chapter, chunk_count in chapter_rows:
                if chunk_count > best_count:
                    best = chapter
                    best_count = chunk_count
            if best is None:
                raise SystemExit("no chapters with chunks found")

            chunks = list(
                await session.scalars(
                    select(Chunk)
                    .where(
                        Chunk.document_id == doc.id,
                        Chunk.chapter_id == best.id,
                    )
                    .order_by(Chunk.document_index)
                )
            )
            return best, chunks, str(doc.id)
    finally:
        await engine.dispose()


def _counts(result: TopicExtractionResult) -> dict:
    topics = 0
    subtopics = 0
    concepts = 0
    objectives = 0
    bad_concepts = 0

    def walk(topic) -> None:
        nonlocal topics, subtopics, concepts, objectives, bad_concepts
        topics += 1
        subtopics += len(topic.subtopics)
        for concept in topic.concepts:
            concepts += 1
            if not isinstance(concept, dict) and not hasattr(concept, "name"):
                bad_concepts += 1
        objectives += len(topic.learning_objectives)
        for sub in topic.subtopics:
            walk(sub)

    for topic in result.topics:
        walk(topic)
    return {
        "topics": topics,
        "subtopics": subtopics,
        "concepts": concepts,
        "objectives": objectives,
        "bad_concept_entries": bad_concepts,
    }


async def _run_one(
    provider: _CountingProvider,
    *,
    chapter_title: str,
    context_text: str,
    settings,
    pricing: tuple[float, float] | None,
) -> dict:
    start = time.perf_counter()
    result = None
    error = None
    try:
        result = await provider.complete_structured(
            system_prompt=TOPIC_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=build_topic_extraction_user_prompt(
                chapter_title=chapter_title,
                chapter_text=context_text,
                max_topics=settings.ai_extract_max_topics,
                max_objectives=settings.ai_extract_max_objectives,
                max_concepts=settings.ai_extract_max_concepts,
                max_prerequisites=settings.ai_extract_max_prerequisites,
            ),
            response_model=TopicExtractionResult,
            temperature=settings.ai_extract_temperature,
            max_output_tokens=settings.ai_extract_max_tokens,
        )
    except Exception as exc:  # noqa: BLE001 - benchmark must not die
        error = f"{type(exc).__name__}: {exc}"

    latency_s = time.perf_counter() - start
    usage = provider.last_usage
    tokens_prompt = usage.prompt_tokens if usage else 0
    tokens_completion = usage.completion_tokens if usage else 0
    cost = 0.0
    if pricing is not None:
        cost = tokens_prompt * pricing[0] + tokens_completion * pricing[1]

    return {
        "model": provider._model,
        "status": "ok" if result is not None else "error",
        "error": error,
        "latency_s": round(latency_s, 2),
        "post_count": provider.post_count,
        "prompt_tokens": tokens_prompt,
        "completion_tokens": tokens_completion,
        "total_tokens": usage.total_tokens if usage else 0,
        "est_cost_usd": round(cost, 6),
        "provider_name": usage.provider if usage else None,
        "counts": _counts(result) if result is not None else None,
    }


async def main() -> None:
    settings = get_settings()
    models = [
        m.strip()
        for m in os.environ.get(
            "OPENROUTER_BENCHMARK_MODELS", ",".join(DEFAULT_MODELS)
        ).split(",")
        if m.strip()
    ]

    chapter, chunks, doc_id = await _load_benchmark_chapter(settings)
    context_text, marker_map = chunk_context.build_marker_annotated_context(
        chunks,
        max_chars=settings.ai_max_context_chars,
    )
    if len(context_text) < settings.ai_min_content_chars:
        print(
            f"[warn] chapter text ({len(context_text)} chars) is below "
            f"AI_MIN_CONTENT_CHARS={settings.ai_min_content_chars}; pipeline "
            "would skip this chapter without an LLM call."
        )

    print(f"document_id={doc_id}")
    print(
        f"chapter={chapter.title} chunks={len(chunks)} "
        f"context_chars={len(context_text)}"
    )
    print(f"models={models}")

    results = []
    for model in models:
        provider = _CountingProvider(
            api_key=settings.openrouter_api_key.get_secret_value(),
            model=model,
            base_url=settings.openrouter_base_url,
            timeout_seconds=settings.openrouter_timeout_seconds,
            max_attempts=settings.openrouter_max_attempts,
            max_retries=settings.openrouter_max_retries,
            retry_base_delay_seconds=settings.openrouter_retry_base_delay_seconds,
            max_retry_delay_seconds=settings.openrouter_max_retry_delay_seconds,
        )
        print(f"\n--- running {model} ---", flush=True)
        try:
            row = await _run_one(
                provider,
                chapter_title=chapter.title,
                context_text=context_text,
                settings=settings,
                pricing=PRICING_PER_TOKEN.get(model),
            )
        except Exception as exc:  # noqa: BLE001
            row = {
                "model": model,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(row)
        for key, value in row.items():
            print(f"  {key}={value}")

    print("\n=== SUMMARY ===")
    width = max(12, max(len(m) for m in models) + 2)
    print(f"{'model'.ljust(width)}{'status':8}{'latency(s)':12}{'posts':6}{'tokens':8}{'cost($)':10}{'topics':8}{'concepts':9}")
    for row in results:
        counts = row.get("counts") or {}
        print(
            f"{str(row['model']).ljust(width)}{str(row['status']):8}"
            f"{str(row.get('latency_s', '-')):12}{str(row.get('post_count', '-')):6}"
            f"{str(row.get('total_tokens', '-')):8}"
            f"{str(row.get('est_cost_usd', '-')):10}"
            f"{str(counts.get('topics', '-')):8}{str(counts.get('concepts', '-')):9}"
        )

    output = os.environ.get(
        "OPENROUTER_BENCHMARK_OUTPUT",
        str(REPO_ROOT / "scripts" / "benchmark_results.json"),
    )
    payload = json.dumps(
        {"chapter": chapter.title, "results": results}, indent=2
    )
    await asyncio.to_thread(
        Path(output).write_text, payload, "utf-8"
    )
    print(f"\nresults written to {output}")


if __name__ == "__main__":
    asyncio.run(main())