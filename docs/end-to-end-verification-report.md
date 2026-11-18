# End-to-End Verification Report

**Project:** SkillUp Action Africa Course Intelligence Platform
**Repository:** `C:\Users\Administrator\ai-course-engine`
**Verification date:** 2026-11-07
**Report status:** Evidence captured for the authoring workflow, QA gates, and local deployment checks. Live Moodle publishing, real-LLM content quality, browser UI execution, and the full learner journey remain unverified.

## 1. Purpose and scope

This report records an actual end-to-end exercise of the application using disposable infrastructure. It answers three questions:

1. Does the implemented authoring pipeline work across HTTP boundaries from document upload to curriculum approval and Moodle publish gating?
2. Do the application's quality and authorization gates behave as documented?
3. Which requirements still depend on external systems or missing product functionality?

The run used the real application code, real PostgreSQL, real Redis, the real ingestion worker, and a deterministic local fake OpenRouter-compatible server. It did **not** use production Moodle, production AI credentials, or production data.

## 2. Verdict summary

| Area | Result | Basis |
| --- | --- | --- |
| Document upload and ingestion | PASS | Real PDF uploaded; ingestion job completed on attempt 1 |
| Text and structure extraction | PASS for born-digital sample | 9 pages, 8 chapters, 24 sections, 17 chunks |
| Topic extraction and planning | PASS with mock content | 128 topics scheduled into exactly 16 weeks |
| Lesson and assessment generation | PASS with mock content | 128 lessons approved; 16 weekly + 1 final assessment generated |
| Content QA | PASS with warnings | QA verdict `warning`, zero error findings |
| QA fail gate | PASS | Corrupted lesson produced QA `fail`; publish returned HTTP 409 `qa_blocked` |
| Curriculum review workflow | PASS | `draft` -> `awaiting_review` -> `approved` |
| Coverage and provenance endpoints | PASS | Coverage 100%; export and source-map returned HTTP 200 |
| Moodle configuration/preflight | PASS for unconfigured state | Preflight `ready=false`, publish HTTP 500 `configuration_error` |
| Live Moodle publish and read-back | BLOCKED / UNVERIFIED | No production credentials or writes were used |
| Real AI generation quality | UNVERIFIED | Fake LLM only |
| Learner enrollment and lesson access | NOT EXERCISED END-TO-END | No published Moodle course existed in the disposable run |
| Final assessment and certification in learner portal | FAIL | No learner attempt or certificate feature exists |

**End-to-end verdict:** `PARTIAL`. The authoring and QA path is operational in a local disposable environment. The platform is not end-to-end acceptance-ready until live Moodle publishing is verified and the learner assessment/certification requirements are implemented.

## 3. Environment

| Item | Value |
| --- | --- |
| Host OS | Windows |
| Python | 3.13.15 (project requires 3.12+) |
| Node / npm | v24.21.0 / 11.19.0 |
| Database | Disposable PostgreSQL 17, `audit-pg`, `127.0.0.1:55432` |
| Queue | Disposable Redis 8, `audit-redis`, `127.0.0.1:56379` |
| API | `http://127.0.0.1:8800` |
| Fake LLM | `http://127.0.0.1:59090/v1` |
| Frontend | Built SPA served from `backend/frontend/dist` |
| Sample document | `storage/sample_ml_textbook.pdf`, 13,433 bytes |
| Moodle | Empty `MOODLE_URL` / `MOODLE_TOKEN` for the main run; fake URL only for the QA-gate test |
| Login rate limiting | Disabled for the disposable run |

The disposable database was migrated with `alembic upgrade head`. The run did not modify the repository's committed application code.

## 4. Evidence artifacts

| Artifact | Path |
| --- | --- |
| Main E2E result JSON | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\e2e_results.json` |
| QA-gate result JSON | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\qa_gate_result.json` |
| E2E driver | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\e2e_driver.py` |
| QA-gate driver | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\qa_gate_check.py` |
| Fake LLM | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\fake_llm.py` |
| Fake LLM request log | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\fake_llm_requests.log` |
| API / worker logs | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\api.log`, `worker.log`, `api_qa_gate.log` |

## 5. Workflow results

### 5.1 Identity, roles, and registration

| Step | Result | Evidence |
| --- | --- | --- |
| Create first admin through CLI | PASS | Admin user `a1657f23-0c45-4434-b97a-a76f6617d90b`; `scripts/create_admin.py` |
| Admin login | PASS | HTTP 200; role `admin`; `redirect_to=/dashboard` |
| Admin creates lecturer | PASS | HTTP 201; role `lecturer`; user `a538c19f-1544-4f99-82ee-7a1954502ec9` |
| Self-registration cannot mint admin | PASS | HTTP 201; returned role `student` |
| Student login | PASS | HTTP 200; `redirect_to=/learn` |
| Student blocked from staff route | PASS | `GET /documents` returned HTTP 403 |
| Learner profile and catalogue | PASS | `GET /learner/profile` 200; `GET /learner/catalog` 200 |

This confirms the documented role split at the HTTP boundary: public registration creates only learners; admin-only creation is required for staff roles; learner routing goes to `/learn`; staff routes reject learners.

### 5.2 Upload and ingestion

| Step | Result | Evidence |
| --- | --- | --- |
| Upload PDF | PASS | Document `fc85adb2-ee53-4f3f-ac6d-48de14fe95a6`, version 1 |
| Hash and size | PASS | SHA-256 `89da495fe20f3bf6779fb0d211444b2604c531a1aea3060abe1f158aeec36f25`; 13,433 bytes |
| Create ingestion job | PASS | Job `e53b67a7-be24-4692-b97d-c5af1138f3f8`, initially `pending` |
| Worker completes job | PASS | `completed`, attempt 1, no error; started 10:51:02.857Z, completed 10:51:11.024Z |
| Document overview | PASS | HTTP 200; page/chapter/chunk/topic counts visible through API |

The background worker processed the document through the real ingestion state machine. No mock was used for extraction, structure detection, or chunking.

### 5.3 Extraction and knowledge structure

| Measure | Result |
| --- | --- |
| Pages | 9 |
| Chapters | 8 |
| Sections | 24 (3 per chapter in the sample) |
| Chunks | 17 |
| Topics | 128 |
| Canonicalization | 128 topics seen, 0 clusters, 0 duplicates flagged, 0 aliases created |
| Dependency graph | HTTP 200; graph build completed |

The sample textbook produced recognizable chapter and section titles from the PDF. Topic titles, learning objectives, concepts, difficulty, workload, and prerequisite titles were populated through the fake LLM.

**Limitation:** the fake LLM intentionally emits 16 unique topics per chapter with a per-chapter hash suffix. This guarantees enough topics for the 16-week planner, but it also means canonicalization and near-duplicate handling were not meaningfully stressed in the main run.

### 5.4 16-week curriculum

| Check | Result |
| --- | --- |
| Curriculum created | PASS; `3b0aa89c-26a9-43da-aef0-9de2c7b63dfb` |
| Requested weeks | 16 |
| Returned units | Exactly 16, week numbers 1-16 |
| Topics per week | 8 every week |
| Total scheduled topics | 128 of 128 |
| Empty weeks | None |
| Learning objectives per week | Present |

The planner satisfied the client's four-month / 16-week requirement in the disposable run. This validates the planner's horizon and allocation behavior, not the pedagogical quality of the generated plan.

### 5.5 Lessons, assessments, and review

| Step | Result | Evidence |
| --- | --- | --- |
| Generate lessons for all weeks | PASS | 128 lessons; no generation errors |
| Lecturer approves lessons | PASS | 128 approved |
| Generate weekly assessments | PASS | 16 weekly assessments |
| Generate final assessment | PASS | 1 final assessment; total 17 |
| Submit curriculum for review | PASS | HTTP 200; state `awaiting_review` |
| Approve curriculum | PASS | HTTP 200; final state `approved` |

Each of the 16 weeks received 8 lessons because the mock supplied 8 planned topics for every week. The final assessment was generated and persisted, but there is no learner-facing endpoint for taking it; see section 8.

### 5.6 Content QA

| Area | Status | Findings |
| --- | --- | --- |
| Coverage | pass | 0 |
| Duplication | warning | 22 `near_duplicate_topic_detected` |
| Provenance | pass | 0 |
| Quality | pass | 0 |
| Learning design | warning | 17 `content_level_missing` |
| Moodle | pass | 0 |

| Field | Value |
| --- | --- |
| QA verdict | `warning` |
| Blocked | `false` |
| Error findings | 0 |
| Total findings | 39 |
| Latest report ID | `404554d0-62ff-4b29-8c58-8b6a66c7cacb` |

The warning-only curriculum was approved successfully. This is correct under the documented severity contract: only `error` findings block approval and publishing.

**Limitation:** the near-duplicate warnings are induced by the mock's repeated topic labels. They are not evidence about real textbook or real-LLM quality.

### 5.7 QA fail gate

The gate was tested separately by deleting all content blocks from the first lesson of the latest curriculum, rerunning QA, then attempting to publish with a syntactically valid but unreachable fake Moodle URL.

| Check | Result |
| --- | --- |
| Corrupted lesson | First lesson `Lesson on Machine Learning Foundations: Foundations [c3470dc6]`; 8 blocks removed |
| QA HTTP status | 200 |
| QA verdict | `fail` |
| QA blocked | `true` |
| Error codes | `empty_lesson`, `shallow_lesson` |
| Findings | 44 total: 2 error, 25 warning, 17 info |
| Publish HTTP status | 409 |
| Publish error code | `qa_blocked` |
| Publish message | `Curriculum failed content-QA; resolve the findings before approving or publishing.` |

This confirms that a hard QA failure blocks Moodle publishing before any Moodle write. It also confirms the intended 409 error shape.

**Related ordering defect:** with `MOODLE_URL` and `MOODLE_TOKEN` unset, the publish route's Moodle service dependency raises `configuration_error` first, so the client receives HTTP 500 rather than the QA gate's 409. The QA assertion is in the route body at `backend/app/api/v1/moodle.py:208`, while the service dependency (`get_moodle_sync_service`) is resolved before the body runs. This does not allow a write, but it produces the wrong error precedence and status when Moodle is unconfigured.

### 5.8 Coverage, export, and source map

| Endpoint | Result |
| --- | --- |
| `GET /curricula/{id}/coverage` | HTTP 200 |
| Coverage | 100.0% |
| Mapped topics | 128 of 128 |
| Lessons | 128 |
| Chapters / sections | 8 / 24 |
| Unresolved topics | 0 |
| `GET /curricula/{id}/export` | HTTP 200 |
| `GET /course-content/lessons/{id}/source-map` | HTTP 200 |

The source map returned actual source chunk text and cited lesson block IDs for the first lesson. This demonstrates that provenance is persisted and retrievable, at least for the generated mock content.

### 5.9 Moodle status and preflight

| Check | Result |
| --- | --- |
| `GET /moodle/preflight` | HTTP 200, `ready=false`, `configured=false` |
| Blocking issue | `not_configured` |
| `POST /moodle/publish/{id}` | HTTP 500, `configuration_error` |
| `GET /moodle/status` | HTTP 200, `configured=false`, `connected=false` |
| `GET /moodle/check` | HTTP 200, `configured=false`, `connected=false` |

The API correctly refused to publish without Moodle configuration. Live read-only and write verification were deliberately not attempted.

**Known inconsistency:** `/moodle/status` uses the real site-info connection result, while `/moodle/check` marks `connected=false` if the category probe throws (`backend/app/api/v1/moodle.py:128-136`). With a partially working Moodle connection, the two screens can disagree.

## 6. Quality checks executed

| Check | Command | Result |
| --- | --- | --- |
| Backend test suite | `python -m pytest -q` from `backend` | 660 passed in 54.42s |
| Frontend production build | `npm run build` from `backend/frontend` | Passed; 1,891 modules; JS 747.61 kB (223.61 kB gzip) |
| Scoped Python lint | `ruff check app tests scripts` from `backend` | All checks passed |
| Repository-root Python lint | `ruff check .` from repo root | 114 errors, almost all in untracked `_state/` scratch scripts; 1 in `scripts/prepare_brand_assets.py` |
| Integration test modules | `backend/tests/integration/` | Present but empty (0 bytes each) |
| Frontend tests | `backend/frontend/package.json` | No test script or test runner configured |

The 660-test suite is largely unit and mocked coverage. The disposable E2E run supplies integration evidence that the empty `tests/integration/` modules do not. There is no browser test harness.

## 7. Defects and observations found during verification

1. **Frontend runtime crash risk in lesson views.** `Button asChild` is given multiple children in `backend/frontend/src/pages/LearnerLesson.tsx:285-288` and `:296-299`, and in `backend/frontend/src/pages/LecturerCourse.tsx:93-96`, `:121-124`, and `:160-163`. Radix `Slot` requires exactly one child. These views are likely to crash when rendered. There is no ErrorBoundary in the SPA. The `asChild` use at `LecturerCourse.tsx:165-169` wraps a single `<a>` element and is structurally valid. Even if `Slot` tolerated multiple children, the two `LearnerLesson` buttons contain no anchor or `Link`, so they would not navigate anywhere.
2. **Duplicate lesson titles can map to the wrong content.** The publisher preserves genuinely different lessons that share a title, but learner content lookup matches the first Moodle page with that title (`backend/app/services/moodle/content.py:99-125`, `:207`). Both pages are published, and the second lesson can open the first lesson's content.
3. **QA gate error precedence.** Unconfigured Moodle produces 500 `configuration_error` before the route-level QA gate can return 409 `qa_blocked`.
4. **Moodle status/check disagreement.** See section 5.9.
5. **No learner final assessment or certification.** Assessment generation is authoring-side only. There is no attempt model, learner assessment endpoint, certificate model, certificate issuance, or certificate download path.
6. **Learner lesson delivery depends on Moodle.** Because no real or fake stateful Moodle was available, enrollment, lesson opening, progress completion, and practical submission were not exercised end-to-end. Unit tests cover these paths, but they were not proven against a published Moodle course.
7. **No OCR.** Scanned/image-only PDFs have no supported extraction path. This is acceptable only if the client confirms all source textbooks are born-digital.
8. **Silent context truncation.** AI analysis uses a bounded per-chapter context (about 6000 characters by default). The truncation is not surfaced to the user, so thin or incomplete topics may appear without a visible warning.

## 8. Explicitly unverified

| Area | Reason |
| --- | --- |
| Live Moodle read-only calls | No production credentials were used |
| Live Moodle course creation, section upsert, page add, verification | Production writes were prohibited |
| Moodle plugin installation and capabilities | Verified only from repository code/docs, not the live site |
| Real OpenRouter/OpenAI output | Fake deterministic provider only |
| Real textbook extraction quality | One small synthetic sample PDF |
| Browser rendering, responsive layout, and navigation | No Playwright/browser automation installed |
| Full learner journey | No published Moodle course in the disposable environment |
| Final assessment taking and certification | Feature does not exist |
| OCR/table extraction | Not implemented |
| Load, security, and penetration testing | Out of scope for this run |

## 9. Reproduction outline

The disposable run is self-contained in the audit directory:

```powershell
C:\Users\Administrator\ai-course-engine\.venv\Scripts\python.exe `
  C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\e2e_driver.py
```

The QA-gate probe mutates the disposable database, so run it only after the main E2E run:

```powershell
C:\Users\Administrator\ai-course-engine\.venv\Scripts\python.exe `
  C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\qa_gate_check.py
```

Both drivers start and stop the API/worker processes themselves. They require `audit-pg` on `127.0.0.1:55432` and `audit-redis` on `127.0.0.1:56379`.

## 10. Conclusion

The core authoring pipeline is demonstrably functional across real HTTP, database, queue, and worker boundaries. The 16-week planner, lesson generation, assessment generation, lecturer approvals, QA severity contract, QA-fail publish block, coverage/export endpoints, and learner/staff authorization boundaries all behaved correctly in the disposable environment.

The evidence does not support client acceptance as a complete delivered platform. The largest gaps are:

- live Moodle publishing and learner content delivery are unverified;
- final assessment and certification are absent from the learner portal;
- the frontend contains a code-level `Button asChild` crash in learner/lecturer lesson views;
- real AI and real textbook quality have not been measured.
