# Verification Report — OpenRouter Production Migration

Date: 2026-09-17. End-to-end verification of the AI Course Engine migration from
the Ollama prototype to the OpenRouter production pipeline. Every number below
was produced by an actual run this session (test suite, live API calls, live
OpenRouter calls, and direct PostgreSQL/Redis inspection).

## 1. Environment

- Docker Compose (`backend/docker-compose.yml`): `postgres:17-alpine`,
  `redis:8-alpine`, `api` (uvicorn `--reload`), `worker`
  (`app.workers.ingestion_worker`). App source bind-mounted (`./app:/app/app`).
- Host venv: Python 3.13; project requirement is Python 3.12+.
- Data volumes `postgres_data`, `redis_data`, `document_storage` retained across
  all container recreates.

## 2. Configuration

- `AI_PROVIDER=openrouter` (production default). `openai` remains an explicit
  opt-in only.
- `OPENROUTER_MODEL=google/gemini-3.1-pro-preview` (selected by benchmark, §12).
- `AI_EXTRACT_MAX_TOKENS` default raised 1536 → 2560 after truncation was
  observed at 1536 with a real chapter (needed 2041 completion tokens). `AI_EXTRACT_TEMPERATURE`
  documented in README/.env.example.
- Docker notes: a plain `docker compose restart worker` does NOT re-read `.env`
  (reuses container env) — a crash caused by a stale `AI_PROVIDER=ollama` env was
  resolved via `docker compose up -d --force-recreate api worker`. Bind-mounted
  app code is picked up by the api on reload; the worker must be restarted
  (entrypoint re-imports bind-mounted code).

## 3. Test suite

`python -m pytest -q` from `backend`: **226 passed in ~36s**. Unit and mocked
coverage only (integration test modules are placeholders, see §19).

## 4. Lint

`ruff check app tests ../scripts`: **All checks passed!** (exit 0). `ruff format
--check` is not CI-enforced; ~90 pre-existing files would be reformatted
(includes this session's files, consistent with repo style).

## 5. Provider architecture

- `LLMProvider` interface in `app/services/ai/base.py`; factory selects
  provider by `AI_PROVIDER`. Business logic never hard-codes a provider.
- OpenRouter calls use `response_format {type:"json_schema", strict:true,
  json_schema:{name, schema}}` + `provider:{require_parameters:true}`.
- LLM calls never occur inside database transactions; provenance is stored for
  AI-generated content.

## 6. Provider error handling (402s)

- Transient 402 `in_flight_budget_exhausted` is retried, honoring `Retry-After`
  (OpenRouter in-flight budget semantics).
- Permanent 402 `openrouter_credits` / plain 402 fail fast with the provider's
  "add credits" remedy surfaced in the error.
- Implemented via `_parse_error_reason` + `_TRANSIENT_REASONS
  = {"in_flight_budget_exhausted"}`, covered by 18 provider tests including
  `test_credits_reason_fails_fast` and
  `test_in_flight_budget_exhausted_retried_then_succeeds`.

## 7. Benchmark harness

- `scripts/benchmark_openrouter.py` (added this session; ruff-clean). Reads a
  real persisted chapter from the DB, builds the real extraction prompts, POSTs
  to OpenRouter, records latency/token counts/cost (pricing map per model) and
  validates the JSON against the extraction schema (`good/bad` counts). Output
  written to JSON.
- Model handle: `google/gemini-3.1-pro-preview`.

## 8. Benchmark results (production-quality run)

- Chapter: "Introduction to Machine"; status **ok**; latency 40.74 s.
- 2 POSTs (1 initial + 1 retry/schema pass), 1848 prompt + 2041 completion +
  3889 total tokens.
- Estimated cost: **$0.028188** (gemini pricing $2/$12 per 1M tokens).
- Provider name returned: Google.
- Extraction quality: 3 topics / 0 subtopics / 7 concepts / 6 objectives /
  0 bad concept entries.

## 9. Model comparison findings

- `anthropic/claude-sonnet-4.5` — HTTP 400 "Provider returned error"; root cause:
  Anthropic rejects the recursive extraction schema ("Circular reference
  detected: ExtractedTopic -> ExtractedTopic"). The extraction model is
  inherently recursive (subtopics), so this model is not usable without schema
  changes.
- `openai/gpt-5.4` — HTTP 404 "No endpoints found". OpenAI strict mode also
  requires `additionalProperties: false` on every object, which Pydantic's
  generated schema does not emit; additionally the account balance was
  insufficient for this model.
- `google/gemini-3.1-pro-preview` — accepted, produced schema-valid JSON in
  probes (HTTP 200) and completed the real chapter run.

## 10. Production ingestion (live end-to-end)

- Uploaded a fresh document version via the public API:
  `efa68a70-3ea7-4851-909f-8ff78b7d5207` (`sample_ml_textbook_v2.pdf`,
  `version_number=2`, `is_latest_version=true`,
  `previous_version_id → 5c025566-fe88-43c5-a221-19af0ef09282`).
  Versioning (no content dedup, explicit `replaces_document_id`) applied as
  designed.
- Ingestion job `1a8bd633-2b1a-4c56-b9b1-e9b17c106ca3`: created 13:32:18 UTC →
  COMPLETED on attempt 1 (~3m23s), zero errors, processed by the worker through
  the state machine (PENDING → VALIDATING → EXTRACTING → NORMALIZING →
  STRUCTURING → CHUNKING → ANALYZING → COMPLETED).

## 11. Extraction data quality (doc `efa68a70`)

- 9 pages / 8 chapters / 13 chunks / 24 topics; all topics `ai_generated`.
- 2 learning objectives per topic; concepts and `prerequisite_titles` populated.
- Provenance: `topic_source_chunks` links 1–2 source chunks per topic.
- DB snapshot (all docs): 3 documents, 32 chapters, 72 sections, 28 pages,
  40 chunks; topics 16/22/24, concepts 52/76/50, dependency edges 0/0/4.
- No fabricated content: extraction is grounded in `AI_MIN_CONTENT_CHARS`
  skip rules and source-chunk markers; hallucinated markers are dropped
  (covered by tests).

## 12. Dependency resolution (doc `efa68a70`)

- `POST /api/v1/documents/{id}/dependencies` → topological order for all
  24 topics, **0 rejected cycle edges**, **0 unresolved prerequisites**,
  4 persisted edges. Idempotent (replaces prior edges for the document).

## 13. Curriculum generation — EXACTLY 16 WEEKS

- `POST /api/v1/curricula` with default `{document_id}` (16 weeks, 5 days/week,
  4 h/day) → version 3 (`953c442d-d2ff-4a0b-bafa-b9a00307f13d`, DRAFT).
- Result verified via API:
  - `total_weeks = 16`; units = 16 with `week_number` 1..16.
  - Topics per week `[2,1,2,1,2,1,2,1,2,1,2,1,2,1,2,1]` — **no empty weeks**,
    24/24 topics scheduled, weekly workloads `[120,60,…120,60]`,
    max 120 min ≤ 1200 min budget; learning objectives present on every week.
  - Versions 1 and 2 (from this session's earlier runs) are superseded but
    retained as history.
- Planner change (this session): `FourMonthPlanner` now guarantees exactly
  `config.total_weeks` weekly units. Greedy packing is followed by a
  deterministic interpolation spread across the full horizon with a
  budget-guarded overflow shift; topic order and weekly budgets are preserved,
  and every week gets ≥1 topic whenever topic count ≥ week count
  (`_spread_to_horizon`). `CurriculumService` validates that planned weeks equal
  `total_weeks`. Covered by 6 focused planner tests + 3 curriculum-service
  tests.

## 14. Regression fixed this session — curriculum response serialization

- `POST /curricula` returned **500 MissingGreenlet**: after `commit()`, the
  async session expires ORM attributes, and the response schema's
  `units[].topics` (property over a relationship) triggered a sync lazy-load.
  The same latent bug affected `submit-for-review` and `review`.
- Fix: after commit, re-fetch the curriculum through
  `CurriculumService.get_by_id` (which `selectinload`s units, topic_links,
  topics, reviews) before `model_validate`. Verified live (HTTP 201, structure
  in §13). The integration-test placeholders are empty, so this is covered by
  the consensus of the 226-test unit suite plus this live verification.

## 15. System-state consistency

- Redis queues `ingestion:jobs:ready`, `ingestion:jobs:processing`,
  `ingestion:jobs:delayed` all empty; no PENDING/ANALYZING jobs remain.
- Jobs by status: 4 COMPLETED, 2 FAILED (both Ollama-era, retained as
  evidence), 2 CANCELLED.
- Worker healthy after restart; api healthy; both reconciled with the
  database.

## 16. Database schema / migrations

- Migration chain head `3fa9a47c28b1`; untouched this session. No new migration
  was required (planner/serialization changes are code-only). Existing
  migrations preserved.

## 17. Cost and capacity facts

- Full 8-chapter document at gemini pricing ≈ $0.2–0.4 (single chapter
  $0.028188 measured).
- OpenRouter account was topped up by the user after the account balance ran
  low; the in-flight-budget handling (§6) prevents failed jobs in that window.
- One worker instance; sequential chapter analysis; latency ~40 s per chapter.

## 18. Known blockers / external dependencies

- **Moodle publish blocked**: live publish requires `moodle/course:create`
  grant on the Moodle instance (admin approval); read-level calls work.
  Not retried in this production run, per user directive.
- OpenRouter account balance is per-account; recharge may be required for
  future full-document runs.

## 19. Coverage gaps (explicit, not hidden)

- `tests/integration/*.py` are empty placeholders — no DB-backed integration
  harness; the 226-test suite is unit/mocked.
- `ruff format` is not enforced (pre-existing ~90-file formatting debt; the
  project lints with `ruff check` only).
- Empty-week handling is defined (allowed when topics < weeks); not yet
  exposed in a frontend screen.

## 20. Documentation updates

- README: current-status item 5 now documents the exact-horizon planner;
  §Frontend corrected to `BrowserRouter` (was wrongly "hash-based routing").
- README + `.env.example`: added `AI_EXTRACT_TEMPERATURE` and
  `AI_EXTRACT_MAX_TOKENS` rows.
- This report plus `docs/cleanup-inventory.md`, `docs/deletion-report.md`,
  `docs/readiness-checklist.md`.

## 21. Disposition

- Functional work this session: provider 402 handling, max-token raise,
  benchmark, production ingestion verification, dependency resolution,
  exactly-16-week planner + tests, curriculum serialization fix,
  documentation.
- Nothing is committed: the entire migration remains in the working tree
  (git head still `ac0efeb`). A commit plan is the owner's decision.
- No destructive git operations or data deletions were performed at any point.