# Readiness Checklist — AI Course Engine Production Handoff

Date: 2026-09-17. 28 concrete items with status and evidence. Legend:
✔ done / ~ partial / ✖ blocked / — n/a. Evidence refers to
`docs/verification-report.md` (§ = section) and the live runs it documents.

## Pipeline & Functional readiness

1. ✔ OpenRouter is the production provider default (`AI_PROVIDER=openrouter`),
   OpenAI preserved as opt-in. — backend/.env; §2.
2. ✔ Production model selected by measured comparison:
   `OPENROUTER_MODEL=google/gemini-3.1-pro-preview`. — §2, §9.
3. ✔ Structured extraction (topics/concepts/objectives/pre-requisites/difficulty)
   validated against schema; 0 bad entries on the benchmark run. — §8.
4. ✔ Recursive-schema limitation understood for claude-sonnet-4.5 (HTTP 400) and
   gpt-5.4 (`additionalProperties` + 404 + unaffordable); documented, not
   papered over. — §9.
5. ✔ `AI_EXTRACT_MAX_TOKENS` raised to 2560; no truncation on real chapter
   (2041 completion tokens measured). — §2, §8.
6. ✔ Transient 402 `in_flight_budget_exhausted` retried (honors `Retry-After`);
   permanent `openrouter_credits` fails fast with remedy message. — §6.
7. ✔ Ingestion async pipeline (Redis worker + state machine) verified end-to-end
   on a fresh document version, attempt 1, no errors. — §10.
8. ✔ Document versioning (supersession, `previous_version_id`) verified with
   `efa68a70` (v2) → `5c025566` (v1 superseded). — §10.
9. ✔ Provenance stored for AI content: `topic_source_chunks` 1–2 links/topic,
   `ai_generated` source type, hallucinated markers dropped. — §11.
10. ✔ Dependency graph builds idempotently; 0 rejected cycles, 0 unresolved
    prerequisites (24 topics). — §12.
11. ✔ Curriculum spans EXACTLY the requested weeks. Live verify: 16 units,
    weeks 1..16, 24/24 topics, no empty weeks, budgets respected. — §13.
12. ✔ Curriculum validates planned-weeks == `total_weeks` before persist. — §13.
13. ✔ Determinism: planner is pure (no DB/AI); identical inputs → identical
    weeks (interpolation + greedy, order preserved). — §13.
14. ✔ Workload/difficulty carried on allocations; weekly budgets enforced. — §13.
15. ✔ Lecturer review workflow implemented (submit → approve/reject) and fixed
    for serialization this session (no 500 on response). — §14.

## Quality gates

16. ✔ Backend test suite green: 226 passed (~36 s) after all changes. — §3.
17. ✔ `ruff check` clean on app, tests, scripts (exit 0). — §4.
18. ~ Integration tests: modules exist but are empty placeholders; coverage is
    unit/mocked. — §19.
19. ~ Formatter: `ruff format --check` not CI-enforced; ~90 pre-existing files
    would be reformatted. — §4.
20. ✔ Failed Ollama-era jobs retained as evidence; not silently deleted. — §5(§deletion-report), §16.
21. ✔ No fabricated content: skip rules (`AI_MIN_CONTENT_CHARS`) + source markers
    + uncertainty preservation documented and tested. — §11.
22. ✔ No LLM calls inside DB transactions; provider abstraction respected. — §5.

## Infrastructure & operations

23. ✔ Containers healthy (postgres/redis/api/worker); app code bind-mounted;
    worker reload requires restart, env changes require forced recreate
    (documented, verified). — §1, §2.
24. ✔ Redis queues empty / no stale PENDING jobs; reconciler stable. — §15.
25. ✔ Migration chain intact (head `3fa9a47c28b1`); no manual schema changes;
    no new migration needed for this session's code changes. — §16.
26. ✔ Cost visibility: full-document estimates ($0.028188/chapter measured;
    ≈$0.2–0.4/doc) documented. — §8, §17.
27. ✖ Moodle LIVE publish blocked externally (`moodle/course:create` grant
    missing); read-level API works. Not attempted in this run per directive. — §18.
28. — Commit state: nothing committed this session; working tree holds the whole
    migration (git head `ac0efeb`). Owner decision to commit is tracked as the
    only open action.

### Summary
Done 24 · Partial 2 · Blocked 1 · N/A 1 (26 actionable). One external blocker
(Moodle grant). No data was deleted; no force git operations were run.

---

## Phase 1 additions (canonicalization, QA, assessments)

Date: 2026-09-25. The suite has grown from 333 to 380 tests and stays green.

| # | Item | Status | Evidence |
|---|---|---|---|
| P1.1 | Topic canonicalization: normalized identity (`canonical_key`), importance, aliases; conservative auto-merge of exact normalized-title duplicates; near-duplicates surfaced, never auto-collapsed | ✔ | `app/services/topics/canonicalization.py`, `test_topic_canonicalization.py` (10 tests) |
| P1.2 | Migration `c3f1a2b9d0e4` (topics columns, self-FK, `quality_reports`, `assessments`, enums); chain intact | ✔ | `alembic/versions/` |
| P1.3 | Content QA: 6 rule domains (coverage, duplication, provenance, quality, learning design, moodle), verdict pass/warning/fail, persisted versioned report | ✔ | `test_qa_rules.py` (14), `test_qa_service.py` (7) |
| P1.4 | QA gates on curriculum approval and Moodle publish (409 `qa_blocked`); Moodle sync code untouched | ✔ | `test_qa_assessment_api.py` |
| P1.5 | Text-book coverage report (topics → lessons/resources/videos) | ✔ | QA service + `/coverage-report` |
| P1.6 | Assessment generation (unit + final), structural validation, objective→lesson→evidence alignment, review workflow | ✔ | `test_assessment_service.py` (8) |
| P1.7 | Frontend: QA run + verdict/findings, coverage, assessment generation & review panels | ✔ | `QAPanel.tsx`, `npm run build` green |
| P1.8 | Full suite green: 380 passed; `ruff check app tests` clean | ✔ | run 2026-09-25 |

Still required for end-to-end (external): OpenRouter/OpenAI key, `YOUTUBE_API_KEY`, Moodle web-service token with `moodle/course:create`, and a real client textbook.