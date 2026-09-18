# Cleanup Inventory — AI Course Engine

Date: 2026-09-17. Scope: everything created, deleted, modified, or left in a stale
state during the migration of AI Course Engine from the Ollama prototype to the
OpenRouter production pipeline. All statements below are grounded in the current
git working tree and live PostgreSQL/Redis state.

## 1. Deleted files (tracked in git, staged/working-tree deletions)

Files removed as part of the provider/pipeline refactor. The full deletion
justification lives in `docs/deletion-report.md`.

| Path | Role replaced by |
|---|---|
| `backend/app/services/ai/embeddings.py` | Embedding feature dropped (not in current priorities) |
| `backend/app/services/ai/llm_client.py` | `app/services/ai/base.py` + `openai_provider.py` + `openrouter_provider.py` |
| `backend/app/services/ai/structured_output.py` | provider `response_format`/validation handling |
| `backend/app/services/content_analysis/chapter_analyzer.py` | `content_analysis/service.py` |
| `backend/app/services/content_analysis/concept_extractor.py` | `content_analysis/service.py` |
| `backend/app/services/content_analysis/difficulty_estimator.py` | `content_analysis/service.py` |
| `backend/app/services/content_analysis/objective_extractor.py` | `content_analysis/service.py` |
| `backend/app/services/content_analysis/prerequisite_detector.py` | `content_analysis/service.py` |
| `backend/app/services/planner/service.py` | `app/services/planner/four_month_planner.py` |
| `backend/app/services/planner/topic_allocator.py` | `app/services/planner/four_month_planner.py` |
| `backend/app/services/planner/week_allocator.py` | `app/services/planner/four_month_planner.py` |
| `backend/app/services/planner/workload.py` | `app/services/planner/four_month_planner.py` |
| `docker-compose.yml` (repo root) | `backend/docker-compose.yml` |
| `docker/backend.Dockerfile` | `backend/Dockerfile` |
| `docker/worker.Dockerfile` | `backend/Dockerfile` |
| `scripts/run_ingestion.py` | API + worker ingestion jobs |
| `scripts/seed_database.py` | API-based document upload |
| `scripts/test_textbook.py` | API-based ingestion tests |

Notes:

- All deletions are git-tracked; none have been force-removed.
- No database data was deleted. `postgres_data` and `redis_data` volumes were
  preserved across every container recreate.

## 2. Added files (untracked in git, part of this migration)

- `AGENTS.md` — project rulebook.
- Alembic migrations: `0dd40f6557cd`, `a5dd290209db` (topics/concepts),
  `b2e9c4f0a7d3` (dependencies), `796ac4bae740` (topic source-chunk provenance),
  `d45a2457f166` (curriculum + course + review), `3fa9a47c28b1`
  (curriculum_description). Migration chain head: `3fa9a47c28b1` (unchanged).
- API: `app/api/v1/overview.py`, `app/api/v1/topics.py`.
- Infrastructure: `app/core/redis.py`.
- Repositories: `app/db/repositories/dependencies.py`, `ingestion_jobs.py`.
- Models: `curriculum_review.py`, `curriculum_unit_topic.py`,
  `topic_source_chunk.py`.
- Schemas: `ai_extraction.py`, `dashboard.py`, `dependency.py`,
  `document_overview.py`.
- AI providers: `app/services/ai/base.py`, `factory.py`, `openai_provider.py`,
  `openrouter_provider.py`.
- Content analysis: `app/services/content_analysis/chunk_context.py`.
- Dependency graph: `app/services/dependency/`.
- Ingestion async pipeline: `app/services/ingestion/job_queue.py`,
  `reconciliation.py`, `state_machine.py`.
- Moodle: `app/services/moodle/status.py`.
- Dashboard: `app/services/overview.py`.
- Frontend: `backend/frontend/` (React/TypeScript/Vite).
- Tests: `backend/tests/unit/test_backoff.py`, `test_chunk_context.py`,
  `test_content_analysis_skip.py`, `test_content_analysis_transactions.py`,
  `test_curriculum_service.py`, `test_dependency_graph.py`,
  `test_dependency_resolver.py`, `test_extraction_validation.py`,
  `test_ingestion_worker.py`, `test_job_queue.py`, `test_lifespan.py`,
  `test_moodle_api.py`, `test_moodle_client.py`, `test_moodle_mapper.py`,
  `test_moodle_sync.py`, `test_openai_provider.py`, `test_openrouter_provider.py`,
  `test_overview_api.py`, `test_overview_service.py`,
  `test_planner_week_limit.py`, `test_reconciliation.py`,
  `test_state_machine.py`, `test_topic_flattening.py`.
- Benchmark script: `scripts/benchmark_openrouter.py` (ruff-clean, repo-mandated).

## 3. Temporary/external artifacts (NOT in the repo)

Session diagnostics live in `%TEMP%\opencode\` and are disposable:

- `inspect_db.py`, `list_jobs.py`, `pending_jobs.py`, `today_jobs.py`,
  `check_analysis.py`, `prod_verify.py`, `verify_prod.py`, `report_snapshot.py`
- `probe_openrouter.py`, `probe3.py` (model capability probes)
- `redis_q.py` (queue inspection)
- `benchmark_results.json` (benchmark output), `curriculum_req.json`,
  `curriculum_resp.json` (API payloads)

These were never part of the repo and can be deleted freely.

## 4. Placeholders deliberately kept (do NOT delete as part of cleanup)

- `backend/tests/integration/test_curriculum.py`, `test_ingestion.py`,
  `test_moodle.py` — empty files reserving the integration test modules. There is
  currently no DB-backed test harness; the suite is unit/mocked.
- `storage/` directory placeholder.

## 5. Live database state (read-only snapshot, 2026-09-17)

| Resource | Count |
|---|---|
| documents | 3 |
| chapters / sections / pages / chunks | 32 / 72 / 28 / 40 |
| topics (top-level included) | 16 + 22 + 24 across docs |
| concepts | 52 + 76 + 50 across docs |
| dependency edges (efa68a70) | 4 |
| ingestion jobs | 4 COMPLETED, 2 FAILED, 2 CANCELLED |
| curricula | 8 versions, all `total_weeks=16` |
| curriculum units / unit-topic links | 57 / 164 |

Deliberately retained (not part of cleanup):

- Failed Ollama-era jobs `6459ccc5…`, `b003c4be…` — kept as historical evidence
  of the migration trigger.
- Superseded curricula (e.g. `efa68a70` v1/v2, `5c025566` v1–v3) — valid draft
  history; leave unless the owner explicitly requests deletion.

## 6. Stale/uncommitted state

- The entire migration is uncommitted in git (many `M`, staged, and untracked
  files as listed above). Nothing has been committed this session; `git log`
  head is still `ac0efeb` ("feat(ingestion): add Redis-backed asynchronous
  ingestion job processing"). The working tree also contains the pre-existing
  `.gitattributes`/`.gitignore`/`Makefile` edits from earlier work.

## 7. Recommended cleanup actions (with owner approval)

1. Delete `%TEMP%\opencode\` diagnostic scripts + JSON artifacts.
2. Decide fate of empty `tests/integration/*.py` placeholders (keep or add a
   DB-backed harness).
3. Purge superseded curricula for `5c025566` only on explicit approval
   (data deletion requires authorization per project rules).
4. Commit the migration in logical commits once the user confirms.