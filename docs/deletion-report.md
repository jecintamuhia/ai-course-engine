# Deletion Report — AI Course Engine

Date: 2026-09-17. This report documents every file deleted during the migration,
the reason for deletion, and what replaced it. No deletions were destructive to
live data; all removed paths are git-tracked deletions recoverable from history.

## 1. AI provider layer (`backend/app/services/ai/`)

Deleted:

- `embeddings.py`
- `llm_client.py`
- `structured_output.py`

Why: The prototype hard-coded an OpenAI-style client and a single `llm_client`
bundle. The current priority mandates provider-agnostic LLM integration, so the
layer was replaced by a provider interface (`base.py:LLMProvider`) with two
concrete implementations: `openai_provider.py` (explicit opt-in only) and
`openrouter_provider.py` (production default). Structured-output handling moved
into each provider (OpenRouter uses `response_format` JSON-schema + OpenAI-style
parametrization; validation/retry logic is inside the provider contract).

`embeddings.py` was removed because embeddings are outside the current feature
priorities (document ingestion → curriculum planning).

## 2. Content analysis per-task modules (`backend/app/services/content_analysis/`)

Deleted:

- `chapter_analyzer.py`
- `concept_extractor.py`
- `difficulty_estimator.py`
- `objective_extractor.py`
- `prerequisite_detector.py`

Why: Each file wrapped one AI extraction step with bespoke prompting and
parsing. Refactored into `content_analysis/service.py` plus `topic_extractor.py`,
which run extraction as a single structured call per chunk (topics, concepts,
objectives, prerequisites, difficulty in one schema), add provenance trimming via
`chunk_context.py`, and respect `AI_MIN_CONTENT_CHARS` to skip header/TOC pages.
Removing the per-task modules eliminated duplicate prompt plumbing and reduced
LLM round-trips from N to 1 per chapter.

## 3. Planner modules (`backend/app/services/planner/`)

Deleted:

- `service.py`
- `topic_allocator.py`
- `week_allocator.py`
- `workload.py`

Why: The prototype split planning across four modules with overlapping logic and
non-deterministic behavior. Consolidation into `four_month_planner.py` provides a
single, pure, deterministic scheduler with `PlanningConfig`, `WeekPlan`, and
`TopicAllocation` types. This session also hardened it to always produce exactly
`config.total_weeks` weekly units (see verification-report §9).

## 4. Containerization moved under `backend/`

Deleted:

- `docker-compose.yml` (repo root)
- `docker/backend.Dockerfile`
- `docker/worker.Dockerfile`

Why: The root compose file shadowed the working `backend/docker-compose.yml` and
the `docker/` Dockerfiles duplicated the build already described in
`backend/Dockerfile`. Single source of truth is now `backend/docker-compose.yml`
(postgres + redis + api + worker, bind-mounted `./app`).

## 5. Prototype scripts (`scripts/` and repo root)

Deleted:

- `scripts/run_ingestion.py`
- `scripts/seed_database.py`
- `scripts/test_textbook.py`

Why: These bypassed the API/worker and staged data directly. Replaced by the
public API (`POST /api/v1/documents`, `POST /api/v1/ingestion/jobs`) and the
Redis-backed worker. The retained `scripts/` tree now contains only
`benchmark_openrouter.py`, a read-only benchmark harness (never modifies the
database).

## 6. Data impact

- The deleted files are the entire deletion footprint. Zero database tables,
  rows, or container volumes were deleted.
- The failed Ollama-era ingestion jobs (`6459ccc5…`, `b003c4be…`) and their
  documents were retained as migration evidence and are not part of this
  deletion.
- The migration chain is intact (head `3fa9a47c28b1`); no migration was deleted
  or altered, and no new migration was required this session.

## 7. Reversibility

- Every deleted path is tracked by git (staged `D` deletions) and can be restored
  from `git log` prior to `ac0efeb`/working tree with `git checkout -- <path>`.
- No `git reset --hard`, `git clean`, or force-push was ever performed.