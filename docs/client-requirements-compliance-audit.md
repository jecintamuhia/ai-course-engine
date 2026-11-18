# Client Requirements Compliance Audit

**Project:** SkillUp Action Africa Course Intelligence Platform
**Repository:** `C:\Users\Administrator\ai-course-engine`
**Original audit:** 2026-11-07
**Remediation pass 1:** 2026-11-10 (findings 6.4, 6.6, 6.7)
**Production-release remediation pass 2:** 2026-11-17 (defect register, D1-D11)
**Status reconciliation pass 3:** 2026-11-18 (current statuses, evidence and open gates)
**Final blocker-closure pass 4:** 2026-11-18 (owner decisions, staging, CI and security evidence)
**Target:** working tree reviewed 2026-11-18
**Current verdict:** **NOT READY FOR PRODUCTION / CLIENT ACCEPTANCE**

> **History is preserved.** Earlier findings and their evidence are not
> rewritten. The 2026-11-10 and 2026-11-17 sections add new evidence and
> restate status. Where a finding changed status, the old text is kept and
> the new status is stated alongside it. The 2026-11-18 pass reconciles stale
> statuses with the verified state; no application tests or live Moodle checks
> were run for this audit edit.

> **2026-11-17 summary (historical).** A second remediation pass fixed a foundational
> live-delivery defect (lesson page bodies were never retrieved from Moodle,
> D11), the lecturer lesson-open 422 (D1), wrong-lesson mapping (D2), stuck
> spinners (D3, D4, D7), stored XSS in lesson HTML (D5), and invalid nested
> interactive markup (D6). Every fix has regression coverage; full backend,
> frontend, typecheck, lint, compile, and build gates are green. The verdict
> remains **NOT READY** because learner final assessment (6.1), certification
> (6.2), live Moodle verification (6.3), course ownership (6.8), token
> lifecycle (6.9), and the empty CI workflows (D8) remain open.

> **2026-11-18 summary.** Phase 3 learner assessment and certification are
> implemented and unit/route tested for objective auto-grading. Phase 4 is
> partial: proxy-header and external-registration policy fixes are in place;
> JWT lifecycle, multi-lecturer ownership and authentication direction remain
> open decisions with draft records. Moodle status/check consistency, OCR-required
> PDF failure and non-fatal analysis warnings are fixed in code. Mocked integration
> tests and CI workflows were added; a later pass execution-verified `tests.yml`
> run #11 after dependency/environment fixes. No staging Moodle, live AI,
> browser/a11y/load/penetration verification or client approval is claimed.
> The verdict remains **NOT READY FOR PRODUCTION**.

## 1. Executive summary and verdict

The authoring pipeline is real and testable. A disposable end-to-end run
covered upload, asynchronous ingestion, structure detection, topic
extraction, a 16-week curriculum, lesson and assessment generation, lecturer
approval, content QA, curriculum approval, coverage/export/source maps, and
role-scoped learner access. QA failure blocks publishing with HTTP 409
`qa_blocked`.

Acceptance is still not supportable because:

1. **Assessment and certification are implemented only for objective
   auto-grading** (6.1, 6.2). Multiple-choice, true/false and short-answer are
   scored; scenario, practical, coding and matching items are shown but excluded
   from scoring, and open-ended manual marking is not implemented.
2. **Live Moodle publishing and learner delivery remain unverified** (6.3).
   The 2026-11-17 pass found and fixed the read path that made delivery
   impossible even against a correct Moodle (D11), but no approved staging
   Moodle exists. The staging checklist is a draft and was not executed.
3. **Course ownership is unimplemented** (6.8); any lecturer can read and
   mark any course. A draft decision record exists but client approval is open.
4. **CI execution is verified but merge enforcement is pending** (D8, 6.17).
   `tests.yml` run #11 passed both jobs; `deploy.yml` is a valid manual-only
   approval gate and performs no production deployment. Making `tests.yml` a
   required check is still an owner action.
5. **The authentication architecture still diverges from the original
    client direction** (6.5) and needs written client acceptance. JWT lifecycle
    and ownership decisions also remain open.
6. **Real AI quality is still unmeasured**; all E2E content used a
   deterministic fake provider.
7. **Browser, accessibility, responsive-device, load and penetration testing
   were not performed.**
8. **`docs/SRD.md`, `docs/architecture.md`, `docs/API.md` and `docs/ERD.md`
   remain empty**, so agreed scope and acceptance evidence is missing.

The strongest parts are the authoring workflow, the 16-week planner, the role
boundary, upload validation, provenance, QA severity handling, stable lesson
navigation, sanitized lesson rendering, learner assessment/certification for
its implemented scope, mocked integration coverage, and backend plus frontend
regression coverage.

**Verdict: NOT READY.** See section 12 for the gate that must close.

## 2. Audit metadata, scope, and evidence rules

### 2.1 Sources reviewed

- `AGENTS.md`, `README.md`, `docs/moodle-integration.md`,
  `docs/moodle-public-access.md`, `docs/production-readiness.md`,
  `docs/verification-report.md`, `docs/readiness-checklist.md`,
  `docs/course-content.md`, `docs/ingestion-pipeline.md`,
  `docs/deployment.md`, `docs/oci-*.md`.
- Backend routes, services, repositories, models, migrations, and tests.
- Frontend routes, pages, components, API client, tests, and build config.
- CI workflow files, Alembic heads, and disposable E2E evidence.
- Prior audit evidence (`e2e_results.json`, `qa_gate_result.json`).
- 2026-11-18 decision drafts, the staging checklist draft, and the authored
  CI workflows.
- Mocked backend integration tests for ingestion, curriculum and Moodle.

### 2.2 Requirements baseline limitation

`docs/SRD.md`, `docs/architecture.md`, `docs/API.md`, and `docs/ERD.md` are
still 0 bytes. There is no approved client SRD. Requirements in section 4 are
reconstructed from `AGENTS.md`, `README.md`, and the Moodle/platform docs.
Anything that depends on unseen client wording is marked
**REQUIRES CLIENT APPROVAL**.

### 2.3 Evidence rules applied in this pass

- A fix is **VERIFIED RESOLVED** only when the code change is present *and* a
  focused automated test executed and passed in the pass that introduced it.
- A fix is **PARTIALLY RESOLVED** when the code is fixed but a real external
  system (Moodle, AI provider, browser) was not exercised.
- **BLOCKED BY EXTERNAL DEPENDENCY** means no credential/instance was
  available. No credential, Moodle response, or deployment URL is fabricated.
- **NOT TESTED** means no execution evidence exists, even if code looks
  correct.
- No production database write, DNS change, credential rotation, destructive
  Git command, or dependency upgrade outside the security fix was performed.
- The 2026-11-18 audit edit executed no tests and no live checks; it reconciles
  statuses against the verified state recorded in section 8.
- No staging Moodle was executed and the production Moodle URL
  `https://elearning.skillupafrica.co.ke` is not verification evidence.

### 2.4 Environment

Windows / PowerShell, Python 3.13 runtime, Node v24.21.0, npm 11.19.0,
`vitest` 2.1.9, `jsdom` 25.0.1, `@testing-library/react` 16.3.3. `rg` is not
installed; searches used the repository Grep tool.

## 3. Status definitions

### 3.1 Requirement statuses (section 4 matrix)

| Status | Meaning |
| --- | --- |
| PASS | Implemented and evidenced by a real run, or by code plus focused automated tests where a live dependency is not required. |
| PARTIAL | Core implementation exists but is incomplete, limited, or unproven under realistic conditions. |
| FAIL | Required behavior is missing or contradicted by the implementation. |
| UNVERIFIED | Implementation may exist but was not exercised. |
| BLOCKED | External access, credential, or owner approval prevents verification. |

### 3.2 Remediation statuses (sections 5-7)

| Status | Meaning |
| --- | --- |
| VERIFIED RESOLVED | Root cause removed; focused regression test passed in the relevant pass. |
| PARTIALLY RESOLVED | Code fixed; dependent external system not exercised. |
| UNRESOLVED | Still defective or missing. |
| NOT TESTED | No execution evidence. |
| BLOCKED BY EXTERNAL DEPENDENCY | Cannot be verified without staging Moodle / real provider / browser. |
| REQUIRES CLIENT APPROVAL | Product or architecture decision owned by the client. |

## 4. Requirements matrix

### 4.1 Ingestion and extraction

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R1 | Upload educational documents | PASS | E2E uploaded a PDF; `backend/app/api/v1/documents.py`; `services/document_storage.py` | PDF and DOCX supported |
| R2 | Validate file type, extension, MIME, size, dedupe | PASS | `backend/app/utils/files.py`; upload returned 13,433-byte document with SHA-256 | Full-file parsing in memory; 50 MB cap |
| R3 | Version documents without losing history | PASS | `previous_version_id`, `version_number`, `is_latest_version` | Covered by code and prior docs |
| R4 | Async ingestion pipeline | PASS | Job `e53b67a7-be24-4692-b97d-c5af1138f3f8` completed attempt 1 | Real worker + Redis queue |
| R5 | Extract text and page structure | PASS | 9 pages from sample PDF | Born-digital only |
| R6 | OCR for scanned documents | FAIL | PDFs with no extractable text fail with an explicit OCR-required error; DOCX already guarded | OCR itself is not implemented — REQUIRES CLIENT SCOPE/APPROVAL |
| R7 | Detect chapters and sections | PASS | 8 chapters, 24 sections | Heuristics; real textbook variety untested |
| R8 | Chunk content semantically | PASS | 17 chunks; provenance used by source maps | Real-textbook chunk quality unverified |

### 4.2 Knowledge extraction and curriculum

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R9 | Extract topics | PASS | 128 topics from 8 chapters | Mock LLM supplied topics |
| R10 | Extract concepts and subtopics | PASS | `ExtractedTopic.subtopics`; self-relationship; concepts persisted | Mock produced concepts, no subtopics |
| R11 | Extract learning objectives | PASS | Objectives per topic and carried into weekly plans | Mock objectives formulaic |
| R12 | Extract prerequisites and resolve dependencies | PASS | HTTP 200; `DependencyGraphService`; dependency tests | Real cross-chapter quality unverified |
| R13 | Estimate difficulty and workload | PASS | Persisted; planner respects budgets | Mock values |
| R14 | Canonicalize topics, preserve uncertainty | PASS | Canonical keys, importance, aliases; near-duplicates surfaced | Weak test under mock data |
| R15 | Generate 4-month / 16-week curriculum | PASS | Exactly 16 units, 8 topics each, 128/128 scheduled | Distribution quality unverified |
| R16 | Enforce weekly workload budgets | PASS | Planner tests; allocations present | Info findings when underfilled |
| R17 | Generate source-grounded lessons | PASS with mock | 128 lessons; source-map endpoint cites chunks | Real grounding/hallucination unverified |
| R18 | Generate weekly and final assessments | PASS for authoring | 16 weekly + 1 final generated; learner attempt flow added (6.1) | Open-ended manual marking not implemented |
| R19 | Persist provenance for AI content | PASS | `source_chunk_markers`, `TopicSourceChunk`, source-map response | Real-LLM completeness unverified |
| R20 | Automated content QA | PASS | Verdict `warning`; 6 areas; persisted report | Warning path + fail path both verified |
| R21 | QA fail blocks approval/publishing | PASS | 409 `qa_blocked`; precedence regression tests (`TestPublishGatePrecedence`) | Re-verified 2026-11-17; no Moodle write occurs |
| R22 | Coverage and export reporting | PASS | Coverage 100%; export/source-map HTTP 200 | Structural, not quality judgment |

### 4.3 Lecturer review and Moodle publishing

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R23 | Lecturer reviews/approves lessons | PASS | 128 lessons submitted and approved via API | Browser UI not exercised |
| R24 | Lecturer reviews/approves assessments | PASS | Endpoints + unit tests | Not in E2E |
| R25 | Curriculum submit/review workflow | PASS | `draft` -> `awaiting_review` -> `approved` | Submit does not run QA; approval/publish do |
| R26 | Publish approved curriculum to Moodle | PARTIAL | Publish pipeline, preflight, mapper, sync, tests | **Updated 2026-11-17:** read path now retrieves Page bodies and preflight requires `mod_page_get_pages_by_courses`. Live publish still not performed. |
| R27 | Idempotent course/section/page publishing | PASS by code and tests | `services/moodle/sync.py`; duplicate-content suppression | Not proven live |
| R28 | Post-publish verification | PASS by code and tests | `_verify_sections`; marker/name tests; page-body identity test | Not proven live |
| R29 | Deliver published lessons to learners | PARTIAL | `MoodleCourseContentService`; UUID-keyed lesson ids; clear missing-body error | **Updated 2026-11-17:** content no longer resolves by raw title; modules expose internal `lesson_id`. Live Moodle unverified. |
| R30 | Moodle preflight with actionable issues | PASS | HTTP 200 `ready=false not_configured`; required functions/capabilities | Live capability inference unverified |
| R31 | Moodle status/health consistency | PASS | `MoodleConnectionCheck.degraded`; `/check` preserves `connected` and sets `degraded` on category-probe failure; invisible category gives an explicit error | No live Moodle verification |
| R32 | No Moodle writes before QA/preflight | PASS | QA-fail returns before writes; regression tests | Re-verified 2026-11-17; precedence pinned |
| R33 | Export fallback for manual import | PASS | `GET /curricula/{id}/export`; `importable: false` | No backup claim |

### 4.4 Learner portal

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R34 | Learner self-registration | PASS | E2E registration role `student` | Google path separate |
| R35 | Role-based post-login routing | PASS | `services/auth/routing.py` | Staff fallback `/learn` only when role not staff |
| R36 | Catalogue and self-enrolment | PASS by code/tests | `/learner/catalog`, `/courses/{id}/enrol`; tests | Not E2E |
| R37 | Enrolment gates content | PASS by code/tests | Course detail requires active enrolment; `require_learner` | Live content path unverified |
| R38 | Lesson completion/progress | PASS by code/tests | Milestones; progress percentage | Not E2E |
| R39 | Practical task hand-in | PASS by code/tests | `POST /courses/{id}/blocks/{block_id}/submit` | Not E2E |
| R40 | Lecturer marks/returns hand-ins | PASS by code/tests | `/lecturer/submissions/{id}/grade`, `/return` | Not E2E |
| R41 | Learner takes final assessment | PARTIAL | `LearnerAssessmentService`; final-assessment, attempt submit/history routes; unit/route tests | 70% pass mark; append-only attempts; best passing attempt wins; objective types only; manual marking not implemented |
| R42 | Certificate issuance/verification | PARTIAL | Issue/list routes and public verification; unique `(user_id, course_id)`; reference `SKU-{YEAR}-{12 uppercase hex}` | Requires 100% approved-lesson completion and one passing attempt; no PDF/download claim |
| R43 | Learner sees only own records | PASS | E2E profile/catalog; staff route 403 as student; self-scoped service | Staff admitted to learner surface by design |
| R44 | Learner opens published lesson content | PARTIAL | `/learner/courses/{id}/content`, `/lessons/{id}/content`; SafeHtml; UUID mapping tests | **Updated 2026-11-17:** title mis-mapping fixed and HTML sanitized. Live Moodle unverified. |

### 4.5 Authentication, security, and roles

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R45 | Four roles | PASS | `UserRole`; routing tests; E2E | Teacher via admin API |
| R46 | Public registration cannot mint staff | PASS | E2E `student`; `register_user` takes no role | Correct |
| R47 | Admin-only user creation | PASS | `/auth/users`; `require_admin` | Correct |
| R48 | Argon2 password hashing | PASS | `core/security.py` | Correct |
| R49 | JWT authentication | PARTIAL | HS256; 720-minute default; no refresh/jti/revocation | Long-lived bearer; no server logout (6.9); draft decision record open |
| R50 | Login rate limiting | PASS | Redis fixed windows; fail-closed 503; `trust_proxy_headers` defaults false and right-most XFF is used only when enabled | No permanent lockout by design |
| R51 | Google sign-in policy | PASS | `get_or_create_external_user` applies registration enablement/allowlist to new external identities | Google disabled without credentials (6.10); auth direction still needs approval (6.5) |
| R52 | Course ownership / lecturer scoping | FAIL | No owner field; lecturer routes only `require_staff` | Any lecturer can access any course (6.8); draft decision record open |
| R53 | Moodle-native learner authentication | FAIL vs original direction | App owns registration/login; Moodle owns delivery | Draft decision record created; needs written client acceptance (6.5) |
| R54 | Production config hardening | PASS | `core/config.py` tests; HTTPS/CORS/secret checks | Not a penetration test |

### 4.6 Branding, documentation, and quality

| ID | Requirement | Status | Evidence | Gap / note |
| --- | --- | --- | --- | --- |
| R55 | SkillUp branding and palette | PASS by assets/config | Brand assets, `brand.ts`, palette CSS | No visual browser verification |
| R56 | Logo not redrawn/recoloured | PASS | `scripts/prepare_brand_assets.py`; packaged PNGs | Root Ruff now passes; no visual browser verification |
| R57 | Backend test suite | PASS | **731 passed in 59.92s (2026-11-18)** | Local final gate; largely unit/mocked |
| R58 | Real integration tests | PARTIAL | 7 mocked tests in `backend/tests/integration/test_ingestion.py`, `test_curriculum.py`, `test_moodle.py` | No live systems or stateful external dependency |
| R59 | Frontend tests | PASS | Full vitest suite passed (2026-11-18) | Component/jsdom only; no browser E2E |
| R60 | Frontend production build | PASS | `npm run build` passed (2026-11-18) | Local gate only |
| R61 | Scoped Python lint | PASS | Local gates plus `tests.yml` run #11 Ruff step passed | Required merge check still to configure |
| R62 | SRD, architecture, API, ERD docs | FAIL | 0-byte documents | No agreed scope or acceptance evidence |
| R63 | SPA error containment and 404 | PASS | `ErrorBoundary` + tests (catch, reset, route change, role home) | **Updated 2026-11-17:** verified by executed tests |
| R64 | Accessible/responsive UI | UNVERIFIED | No browser/a11y run | Not performed |

## 5. Defect register (production-release pass 2026-11-17)

| ID | Component | Observed | Expected | Root cause | Severity | Fix | Regression test | Verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | Lecturer lesson view | Opening a lesson called `GET /lecturer/courses/{id}/lessons/{cmid}` and returned 422 | Opens the lesson | Lecturer page passed Moodle `cmid` into a backend route typed `uuid.UUID`; `api.lecturerLessonContent` expects a lesson UUID | CRITICAL | Navigate and fetch by `module.lesson_id`; disable opening when unresolved | `LecturerCourse.test.tsx` "opens a lesson by its internal lesson id" | VERIFIED RESOLVED |
| D2 | Learner course page | Lessons mapped to Moodle pages by raw title; duplicate/disambiguated titles produced wrong content or "Content not available" | Correct lesson per page | `lessonByTitle` keyed on mutable Moodle page names | HIGH | Structure response now carries `lesson_id`; frontend keys by `lesson_id`; backend resolves marker then computed name | `test_course_structure_exposes_internal_lesson_ids`; LearnerCourse mapping | VERIFIED RESOLVED |
| D3 | Learner lesson retry | Failed load left spinner stuck and swallowed the error | Retry re-fetches and recovers | `handleRetry` did not reset/clear state and ignored rejection | HIGH | `try/catch/finally` sets error and clears loading | `LearnerLesson.test.tsx` "recovers from a failed lesson load" | VERIFIED RESOLVED |
| D4 | Learner course retry | Retry fired `void load()` with no catch/finally | Retry re-fetches and recovers | Unhandled rejection, loading never reset | MEDIUM | Shared `handleRetry` with `try/catch/finally` | Code review + build/test gates | VERIFIED RESOLVED |
| D5 | Lesson HTML | Moodle Page HTML rendered via `dangerouslySetInnerHTML` in learner and lecturer views | Untrusted HTML sanitized | No sanitizer; Moodle admins can edit page bodies | HIGH (security) | `SafeHtml` component (DOMPurify; forbids script/iframe/object/embed/form/base, `srcdoc`, `formaction`) | `SafeHtml.test.tsx` (script/onclick/javascript: stripped) | VERIFIED RESOLVED |
| D6 | Prev/next controls | `<Link>` wrapping `<Button>` created nested interactive elements | One interactive element per control | `asChild` pattern misused | MEDIUM | `Button asChild` + `Link` | Lecturer/Learner navigation tests | VERIFIED RESOLVED |
| D7 | Lecturer lesson retry | Retry swallowed rejection and could leave no feedback | Retry re-fetches and shows outcome | Unhandled rejection in `handleRetryLesson` | MEDIUM | `try/catch/finally` | `LecturerCourse.test.tsx` "recovers when a lesson fails to load" | VERIFIED RESOLVED |
| D8 | CI | `.github/workflows/tests.yml`, `deploy.yml` are 0 bytes | Automated test/lint/build gate | Workflows never authored | HIGH (release process) | `tests.yml` authored with backend/frontend gates; `deploy.yml` is a manual-only approval gate with no production deployment; test deps/env fixed | `tests.yml` run #11 passed both jobs | RESOLVED for execution; required merge check pending |
| D9 | Authorization | Any lecturer can read/mark any course; no owner model | Enforced ownership or accepted single-tenant model | No ownership field; staff-only gate | HIGH (security/product) | Draft `docs/decision-record-course-ownership.md`; no schema/code change | Ownership tests absent | UNRESOLVED / REQUIRES CLIENT APPROVAL |
| D10 | Learner assessment/certification | No attempts, scoring, results, certificate, or verification | Learner takes final assessment and receives certificate | Never implemented | CRITICAL (product) | Service, routes, models and tests added for objective auto-grading and verifiable certificates | Learner assessment service/API tests | VERIFIED RESOLVED for implemented scope; open-ended manual marking NOT IMPLEMENTED |
| D11 | Moodle lesson content | `core_course_get_contents` does not return Page bodies, so every lesson would render empty against a real Moodle | Retrieve the Page body | Read path only used core contents (file list/index link) | CRITICAL (foundational) | Added `page_content.py` using `mod_page_get_pages_by_courses`; merged bodies in read and sync; preflight requires the function; missing body raises a clear `MoodleIntegrationError` instead of empty content | Client, content, sync, and preflight tests | VERIFIED RESOLVED (code); live Moodle BLOCKED BY EXTERNAL DEPENDENCY |

## 6. Detailed findings by severity

### 6.1 Critical: learner final assessment is implemented (objective scope) — PARTIALLY RESOLVED 2026-11-18

`AGENTS.md:23` requires final assessment and certification. The 2026-11-17
finding was that `learner.py` exposed no attempt, answer, score or result
endpoint; assessment generation was staff-gated.

**2026-11-18 status:** `LearnerAssessmentService` and learner routes provide
final-assessment retrieval, attempt submission, attempt history, a 70% pass
mark, append-only attempts and best-passing-attempt selection. Auto-grading
covers `multiple_choice`, `true_false` and `short_answer` with a stored correct
answer. Scenario, practical, coding and matching are displayed but excluded
from scoring; open-ended manual marking is **NOT IMPLEMENTED**. Duplicate or
concurrent submissions are protected by unique
`(assessment_id, enrolment_id, attempt_number)` and return
`AssessmentSubmissionError`. Unit and route tests exist.

### 6.2 Critical: certification is implemented — PARTIALLY RESOLVED 2026-11-18

The 2026-11-17 finding was that no certificate model, migration, service or
endpoint existed.

**2026-11-18 status:** certificate issue/list and public verification are
implemented and unit/route tested. Eligibility requires 100% approved-lesson
completion and one passing attempt. References use
`SKU-{YEAR}-{12 uppercase hex}`; issuance is idempotent by unique
`(user_id, course_id)`. The verified state covers issuance, listing and
verification only; no PDF/download claim is made.

### 6.3 Critical: live Moodle delivery is unverified — BLOCKED BY EXTERNAL DEPENDENCY

The pipeline is implemented and unit-tested, but no live write was performed.
`docs/moodle-integration.md:207-211` records a live course where only Week 1
has page resources. The 2026-11-17 pass removed a hard blocker (D11), but
verification still requires an approved Moodle. `docs/staging-integration-checklist.md`
is a drafted, **NOT EXECUTED** checklist; no staging Moodle exists. The
production URL `https://elearning.skillupafrica.co.ke` must never be used for
verification.

**Required action:** use a non-production Moodle, install the bundled plugin,
grant `mod/page:view` and the `local_ai_course_engine_*` functions, run
preflight, publish 16 weeks, verify every section/page, enrol a learner, and
open every lesson.

### 6.4 Critical: frontend `asChild` crash in lesson views — **VERIFIED RESOLVED 2026-11-10**

Radix `Slot` requires exactly one child. Multi-child usages existed at
`LearnerLesson.tsx:285-288`, `:296-299` and `LecturerCourse.tsx:93-96`,
`:121-124`, `:160-163`. There was no ErrorBoundary; two LearnerLesson buttons
had no anchor.

**Resolution:** every affected button wraps one `<Link>`; an app-level
`ErrorBoundary` wraps the router and resets on route change. Component tests
cover catch, reset, route-change recovery, role-aware home links, and back
buttons. The 2026-11-17 suite had 21 passing tests; the full vitest suite
passed again on 2026-11-18.

**Remaining:** real-browser, accessibility, responsive-device, load and
penetration testing were not performed.

### 6.5 High: learner authentication diverges from the original direction — REQUIRES CLIENT APPROVAL

The original direction was Moodle-native learner sign-in. The delivered app
implements local student registration, password login, optional Google
sign-in, and its own progress/records database.

**Impact:** product/architecture change; Moodle and portal identity/
enrolment can diverge.

**2026-11-18 status:** `docs/decision-record-authentication-direction.md` is a
draft record only; it does not grant approval. Client approval is still
required for 6.5/R53.

**Required action:** written client approval or architecture change; document
identity linking, enrolment sync, and deprovisioning.

### 6.6 High: QA gate returns the wrong error when Moodle is unconfigured — **VERIFIED RESOLVED 2026-11-10**

The QA gate ran in the route body but `get_moodle_sync_service` depended on a
client that raised `configuration_error` when Moodle was unset; FastAPI
resolved it first.

**Evidence before fix:** E2E publish with empty Moodle config returned 500
`configuration_error`; QA-fail with a configured fake Moodle returned 409
`qa_blocked`.

**Resolution:** `MoodleSyncService` accepts an optional client and defers the
requirement to `_require_client()`; the dependency reads
`request.app.state.moodle_client`; the publish route validates the curriculum
and runs QA before any Moodle operation. Tests: `TestPublishGatePrecedence`
and `TestUnconfiguredClient`.

**Independent re-check 2026-11-17:** full suite passes (697 tests), including
both orderings; no publish is recorded in either case.

### 6.7 High: duplicate lesson titles can open the wrong content — **VERIFIED RESOLVED 2026-11-10**

The renderer kept genuinely different lessons with the same title and
published both, while lookup matched the first page with that title across
the course, and verification only checked for a page with the name.

**Resolution:** a stable marker `<!-- skillup-lesson-id: {lesson_id} -->` is
embedded in every lesson page; page names are disambiguated course-wide (raw
title → `"(Week N)"` → `"(Week N, Lesson K)"` → counter); identical-rendered
content within a unit collapses to one page. Content resolution follows
marker → computed unique name → legacy unique title → content equality, and
ambiguous legacy cases raise a detailed `LessonNotFound`. Sync/verification
use marker-or-name.

**2026-11-17 extension (D1/D2):** the course-structure response now exposes
the resolved internal `lesson_id` per module; the learner and lecturer portals
navigate by that id instead of by `cmid` or title. Tests:
`test_course_structure_exposes_internal_lesson_ids`,
`test_course_structure_leaves_unidentifiable_page_unresolved`, and the
portal navigation tests.

**Limitation:** the plugin has no `update_page`, so legacy pages published
before the marker cannot be rewritten; they are matched by name/content
equality until a fresh republish.

### 6.8 High: no course ownership or lecturer scoping — UNRESOLVED / REQUIRES CLIENT APPROVAL

`Course` has no owner field. Lecturer endpoints require only
`require_staff`; all staff can access all courses and submissions.

**Independent check 2026-11-17:** confirmed in `models/course.py` and
`api/v1/lecturer.py`; no scoping predicate exists in the repositories.

**Impact:** any lecturer can read or mark any course. Acceptable only for an
explicitly accepted single-tenant deployment.

**2026-11-18 status:** `docs/decision-record-course-ownership.md` is a draft
record only; no schema or code change and no approval resulted from it.

**Required action:** add ownership/assignment and enforce it, or document and
obtain written acceptance of the single-tenant trust model. No pre-delivery
schema change was made because that decision is the client's.

### 6.9 High: long-lived JWT with no revocation or logout — UNRESOLVED

`create_access_token` sets `sub`, `role`, `iat`, `exp`; default 720 minutes.
No refresh token, `jti`, revocation list, or server logout. The SPA stores the
token client-side and does not act on expiry.

**2026-11-18 status:** `docs/decision-record-jwt-lifecycle.md` is a draft
record only; no token code or configuration changed and no approval was given.

**Required action:** short-lived access + refresh/rotation, or server-side
revocation/logout, plus SPA expiry handling.

### 6.10 Medium: Google sign-in bypasses registration policy — VERIFIED RESOLVED 2026-11-18

The 2026-11-17 finding was that `get_or_create_external_user` created a
`STUDENT` on first Google sign-in without checking
`AUTH_REGISTRATION_ENABLED` or allowed domains.

**Resolution:** external sign-in now applies registration enablement and domain
policy to new identities in `backend/app/services/auth/service.py`; tests cover
the disabled and allowlist paths. Google remains disabled without credentials.
The separate Moodle-vs-portal authentication direction remains open (6.5).

### 6.11 Medium: Moodle status and check can disagree — VERIFIED RESOLVED (code) 2026-11-18

The 2026-11-17 finding was that `/moodle/check` set `connected=false` when a
category probe failed.

**Resolution:** `MoodleConnectionCheck.degraded` separates transport health
from category visibility. `/check` preserves `connected` and sets `degraded`
on category-probe failure; an invisible configured category returns an
explicit error. Code and tests are in place. No live Moodle verification was
performed.

### 6.12 Medium: no OCR and silent context truncation — PARTIALLY RESOLVED 2026-11-18

**OCR:** PDFs with no extractable text now fail with an explicit OCR-required
error; DOCX input was already guarded. OCR itself is **NOT IMPLEMENTED** and is
blocked on client scope/approval.

**Warnings:** analysis responses now include non-fatal warnings for context
truncation (`omitted_chunks`, `total_chunks`, `max_chars`), insufficient
content and empty chapters. Evidence: `AnalysisWarningRead`,
`backend/app/services/content_analysis/service.py` and the relevant unit/API
tests. No real AI provider was used.

### 6.13 Medium: requirements and API documentation are empty — UNRESOLVED

`docs/SRD.md`, `docs/architecture.md`, `docs/API.md`, `docs/ERD.md` are
0 bytes.

**Required action:** produce and approve them with agreed scope and acceptance
evidence; reconcile with the learner/Moodle split.

### 6.14 Medium: integration and CI tests are missing — PARTIALLY RESOLVED 2026-11-18

`backend/tests/integration/test_ingestion.py`, `test_curriculum.py` and
`test_moodle.py` now add 7 mocked integration tests; no live systems are
exercised. Frontend tests exist (R59), but browser E2E is absent. CI workflows
were authored (D8), but GitHub Actions execution is **NOT VERIFIED**.

**Required action:** database-backed API integration tests, browser role
journeys, a stateful fake/approved Moodle, and verified CI wiring.

### 6.15 Low: repository-root Ruff includes untracked scratch files — VERIFIED RESOLVED 2026-11-18

Both scoped `python -m ruff check app tests scripts` and root
`python -m ruff check .` now pass.

### 6.16 Critical (new): lesson content was never retrieved from Moodle — **VERIFIED RESOLVED (code)**

`core_course_get_contents` returns a Page module's file contents (a download
link to `index.html`), not the body. Lesson content and the identity marker
therefore never reached the portal or post-publish verification, so a live
course would show empty lessons and verification would fail or pass on names
alone.

**Resolution:** `backend/app/services/moodle/page_content.py` calls
`mod_page_get_pages_by_courses`, keyed by course-module id, and overlays the
body onto core contents. Applied in both read (`content.py`) and sync
(`sync.py`). Preflight now requires the function (`mod/page:view`, since 3.3).
When a body is unavailable, content lookup raises a detailed
`MoodleIntegrationError` (lesson, page name, cmid) instead of returning empty
HTML. Tests: client parameter test, content-body merge, sync identity from
page bodies, and preflight requirement.

**Limitation:** the connected Moodle token must expose
`mod_page_get_pages_by_courses`; the portal reports this clearly through
preflight. Live behaviour is BLOCKED BY EXTERNAL DEPENDENCY.

### 6.17 High (new): no automated CI gate — RESOLVED for execution 2026-11-18

`.github/workflows/tests.yml` now authors backend and frontend gates, and
`.github/workflows/deploy.yml` is a valid manual-only approval gate that
performs **NO production deployment**. GitHub Actions execution is **VERIFIED**:
run #11 completed with both jobs passing after the test dependency and
`ENVIRONMENT=testing` fixes recorded in section 8.1.

**Remaining owner action:** make `tests.yml` a required check so it blocks
merge on failure.

## 7. Independent verification of prior fixes

| Claim | Method | Result |
| --- | --- | --- |
| 6.6 QA gate precedes Moodle configuration errors | Read `MoodleSyncService`/dependency wiring; gate tests executed in the 2026-11-17 run | VERIFIED RESOLVED |
| 6.7 Duplicate titles open the right lesson | Read marker/name/collapse chain and `_assign_lesson_ids`; content, mapper, lessons, sync, API and portal tests | VERIFIED RESOLVED |
| 6.8 Ownership exists | Searched `models/course.py`, `api/v1/lecturer.py`, repositories; read draft decision record | UNRESOLVED / REQUIRES CLIENT APPROVAL (no owner/scoping) |
| 6.10 External registration policy | Read `get_or_create_external_user` and auth tests | VERIFIED RESOLVED |
| 6.11 Moodle check consistency | Read `MoodleConnectionCheck`, `/check` route and moodle API tests | VERIFIED RESOLVED (code); live BLOCKED BY EXTERNAL DEPENDENCY |
| 6.12 OCR-required failure and warnings | Read text extractor, analysis warnings and unit/API tests | PARTIALLY RESOLVED; OCR BLOCKED BY CLIENT APPROVAL |
| 6.15 Root Ruff | Scoped and root `ruff check` results in section 8 | VERIFIED RESOLVED |
| 6.17 CI gate | Public GitHub API run #11 and jobs | VERIFIED PASS; required check pending |
| R21 QA fail blocks publish | Gate-precedence tests | PASS |
| R26 Publish to live Moodle | No staging instance available; checklist not executed | BLOCKED BY EXTERNAL DEPENDENCY |
| R32 No writes before QA/preflight | Read route order; gate tests | PASS |
| R41/R42 Assessment and certification | Read service/routes; unit/route tests | PARTIAL (objective auto-grading only) |
| R44 Learner opens content | UUID mapping + SafeHtml; content/service and portal tests | PARTIAL (live unverified) |
| R57/R59/R60/R63 quality gates | Verified state recorded in section 8; this audit edit ran no commands | PASS (local) |

## 8. Verification evidence (2026-11-17; final local gates 2026-11-18)

2026-11-17 exit codes were captured from the shell. The 2026-11-18 final gates
were executed in the working tree after all remediation edits; the audit text
edit itself did not execute commands.

| Command | Result | Exit |
| --- | --- | --- |
| `python -m pytest -q` (backend, 2026-11-17) | **697 passed in 43.21s** | 0 |
| `npm run test` (frontend, 2026-11-17) | **4 files, 21 tests passed** | 0 |
| `python -m alembic heads` (2026-11-17) | `9d1e4c7a2b30 (head)` (single head) | 0 |
| `python -m pytest -q` (backend, 2026-11-18) | **731 passed in 59.92s** | 0 |
| `npm run test -- --run` (frontend, 2026-11-18) | **5 files, 23 tests passed in 8.64s** | 0 |
| `npm run typecheck` (2026-11-18) | Passed | 0 |
| `npm run build` (2026-11-18) | Passed | 0 |
| `python -m ruff check app tests scripts` (2026-11-18) | Passed | 0 |
| `python -m compileall -q app` (2026-11-18) | Passed | 0 |
| `python -m ruff check .` (2026-11-18) | Passed | 0 |
| `python -m alembic heads` (2026-11-18) | `f1a2b3c4d5e6 (head)` (exactly one head) | 0 |

Baseline before the 2026-11-17 pass: 690 backend tests, 14 frontend tests,
same single Alembic head. That pass added 7 backend tests and 7 frontend
tests, and modified 1 backend test that previously asserted the now-corrected
empty-content behaviour. The current Alembic head is `f1a2b3c4d5e6`.

New/changed test coverage in the 2026-11-17 pass:

- `backend/tests/unit/test_moodle_client.py`: `TestGetPagesByCourses`
  (function name, `courseids[0]`, non-dict guard).
- `backend/tests/unit/test_moodle_content.py`: missing-body error, page-body
  merge via `mod_page_get_pages_by_courses`, structure `lesson_id`
  assignment, unresolved page.
- `backend/tests/unit/test_moodle_sync.py`: verification identity supplied by
  page bodies when core omits content.
- `backend/tests/unit/test_moodle_preflight.py`: missing
  `mod_page_get_pages_by_courses` is reported with `mod/page:view`.
- `backend/frontend/src/components/shared/SafeHtml.test.tsx`: keeps markup,
  strips scripts/handlers, drops `javascript:` links.
- `backend/frontend/src/pages/LearnerLesson.test.tsx`: retry after failure.
- `backend/frontend/src/pages/LecturerCourse.test.tsx`: open by internal id,
  retry, unresolved page disabled.

2026-11-18 added/updated coverage:

- `backend/tests/unit/test_learner_assessment_service.py` and
  `backend/tests/unit/test_learner_assessment_api.py`: assessment scoring,
  attempts and certificate routes.
- `backend/tests/integration/test_ingestion.py`, `test_curriculum.py` and
  `test_moodle.py`: 7 mocked integration tests; no live systems.
- `backend/tests/unit/test_moodle_api.py`: `degraded` health response.
- `backend/tests/unit/test_rate_limit_ip.py`: proxy-header trust behaviour.
- `backend/tests/unit/test_auth.py`: external sign-in registration policy.
- `backend/tests/unit/test_text_extractor.py`, `test_content_analysis_skip.py`
  and `test_topics_api.py`: OCR-required failure and non-fatal warnings.

**What these results do not prove:** live Moodle behaviour, real AI output,
GitHub Actions execution, staging execution, browser rendering, accessibility,
responsive-device behaviour, load, penetration resistance, open-ended manual
marking, or client approval.

### 8.1 Final blocker-closure pass (2026-11-18)

- **Client decisions:** [`client-decision-register.md`](client-decision-register.md)
  now records 21 unresolved decisions. None has written client approval. Owner
  direction recorded in this workspace on 2026-11-18 is that objective-only
  assessment is acceptable; this remains pending written approval. The register
  also records the exact policy questions required before manual assessment
  marking can be implemented. No identity, enrolment, assessment or
  certification policy was invented.
- **Staging Moodle:** no non-production Moodle exists. `backend/.env` contains a
  production `MOODLE_URL`/`MOODLE_TOKEN`, which is not verification evidence and
  was not used. No live Moodle API call, publish, read-back, learner progression
  or certificate verification was performed.
- **Manual marking:** the assessment schema has seven item kinds, but the
  scoring service auto-grades only `multiple_choice`, `true_false`, and
  `short_answer`. Scenario, practical, coding, and matching items are displayed
  but excluded; there is no attempt-level grader, mark, feedback or marking
  status field. Generic "open-ended" is not an item kind. No manual marking was
  added because the grading policy is undefined.
- **GitHub Actions:** after pushing the working tree, `tests.yml` run #9 (id
  `44269524521`) executed both jobs but failed at Ruff because `ruff` was absent
  from `backend/requirements/test.txt`. Run #10 (id `44269907260`) passed Ruff,
  byte-compile and Alembic then failed at pytest with exit code 4 because the
  workflow used invalid `ENVIRONMENT=test` and `fakeredis`/`reportlab` were
  missing from test requirements. Fixes were applied: `ENVIRONMENT=testing` and
  pinned `ruff==0.16.5`, `fakeredis==2.37.1`, `reportlab==5.0.1`. Run #11 (id
  `44271152336`, commit `3e5ec8abd8c2ec7ce84cd82e12680b332a98f04c`, completed
  `2026-11-18T08:56:23Z`) concluded `success` with both jobs passing. The
  workflow now executes; merge enforcement still requires making the check
  required. `gh` is not installed/authenticated locally; evidence was read from
  the public GitHub API.
- **Browser and security testing:** Chrome, Edge, and Firefox binaries exist,
  but no Playwright/Cypress/axe/Lighthouse/Puppeteer/chromedriver runtime or
  config exists; no browser, accessibility, responsive-device, load, or
  penetration test was performed. `npm audit --omit=dev --audit-level=high`
  reported 14 advisories (3 moderate, 11 high), including a high-severity
  `picomatch` ReDoS chain and moderate `postcss-selector-parser` and
  `react-router` advisories. `pip-audit` is not installed, so no Python
  dependency audit was run. Dependency remediation was not applied because the
  known `tailwindcss` fix is breaking and no upgrade policy was approved.

## 9. Security and data-integrity review

### 9.1 Addressed in the 2026-11-17 pass

- **Stored XSS (D5):** lesson HTML is now sanitized by `SafeHtml`
  (DOMPurify) in both portals. Tags `script`, `iframe`, `object`, `embed`,
  `form`, `base` and attributes `srcdoc`, `formaction` are forbidden;
  `javascript:` URLs are removed by DOMPurify. Regression tests execute the
  sanitizer.
- **Authorization on content ids (D1):** the lecturer path now sends internal
  lesson UUIDs; the backend still enforces `require_staff` and derives the
  course from the route id, so a lesson id cannot escape its course scope.
- **Error disclosure:** missing Moodle bodies produce a specific integration
  error (lesson/page/cmid) without tokens or internal stack data.

### 9.1a Addressed in the 2026-11-18 reconciliation

- **External registration policy:** first Google/external sign-in now obeys
  registration enablement and allowed-domain rules.
- **Proxy trust (`R50`):** `trust_proxy_headers` defaults to false; only the
  right-most `X-Forwarded-For` value is used when explicitly enabled.
- **Moodle health consistency (`6.11`):** `degraded` is separate from
  `connected`, and an invisible configured category produces an explicit error.
- **Assessment/certificate integrity:** attempts are append-only with a unique
  `(assessment_id, enrolment_id, attempt_number)` key; certificates are
  idempotent by unique `(user_id, course_id)`.
- **Extraction transparency:** empty-text PDFs fail explicitly with an
  OCR-required message, and analysis warnings report truncation,
  insufficient content and empty chapters.

### 9.2 Open security items

| Item | Status | Note |
| --- | --- | --- |
| Course ownership (6.8/D9) | UNRESOLVED / REQUIRES CLIENT APPROVAL | Any staff user can access any course; draft record only |
| JWT lifetime/revocation (6.9) | UNRESOLVED / REQUIRES CLIENT APPROVAL | 720-minute bearer token, no logout/revocation; draft record only |
| Google registration policy (6.10) | VERIFIED RESOLVED | External sign-in now applies enablement/allowlist |
| Login rate limiting (R50) | PASS | Redis windows; proxy trust off by default, right-most XFF only when enabled |
| Moodle status/check consistency (6.11) | VERIFIED RESOLVED (code) | `degraded` flag; no live Moodle verification |
| OCR for scanned PDFs (6.12) | BLOCKED / REQUIRES CLIENT APPROVAL | Explicit OCR-required error; no OCR implementation |
| CI security gate (D8/6.17) | PASS for execution | `tests.yml` run #11 passed; required merge check pending |
| Staging execution (6.3) | NOT EXECUTED | Draft checklist only; no staging Moodle exists |
| Real browser/a11y/load/penetration test | NOT TESTED | Not performed |

### 9.3 Data integrity

- The 2026-11-17 pass made no schema change; the current Alembic head is
  `f1a2b3c4d5e6` with exactly one head (no branch divergence).
- No production database was read or written in the audited passes; no data was
  deleted.
- The 2026-11-17 read path only overlays Page bodies onto API responses; it
  does not mutate stored curriculum or learner records.
- Assessment attempts are append-only and certificates are unique per learner
  and course; duplicate/concurrent submissions and repeat issuance are handled
  explicitly.
- Failure behaviour is explicit: a missing page body raises instead of
  persisting or serving an empty lesson; text-free PDFs fail with an
  OCR-required error.

### 9.4 Dependency and configuration

- One dependency added: `dompurify` `^3.4.18` (security-critical, justified by
  D5); no other upgrade was made.
- No secret, token, or credential was written to the repository or logs.
- Production readiness checks in `core/config.py` remain as previously
  audited (HTTPS/CORS/host/secret validation).

## 10. Test coverage assessment

| Layer | Coverage | Reality check |
| --- | --- | --- |
| Backend unit | 731 passed in 59.92s (2026-11-18) | Strong on services, auth, curriculum, Moodle logic (mocked HTTP) |
| Assessment/certification | Unit and route tests for service, attempts, scoring and certificates | Objective items only; open-ended manual marking not implemented |
| Backend integration | 7 mocked tests in ingestion, curriculum and Moodle (R58) | No database-backed staging request tests |
| Moodle integration | Mocked HTTP + fake clients | No stateful fake or staging Moodle |
| Frontend component | Full vitest suite passed (2026-11-18) | Lesson/course navigation, retry, sanitizer, error boundary; no browser E2E |
| Frontend browser E2E | None | Role journeys not automated |
| Migrations | Single head `f1a2b3c4d5e6` | No upgrade/downgrade rehearsal on a real PostgreSQL instance |
| Lint/type/build/compile | All green locally and in `tests.yml` run #11 | Required merge check still pending |

**Assessment:** backend logic is the strongest layer; Moodle delivery, browser
behaviour and external dependencies are the weakest. The new tests close the
specific defects recorded in this audit but do not replace a staging
environment, real AI provider, client approval, or browser/accessibility/load/
penetration verification.

## 11. External dependencies and owner decisions

| Item | Owner action | Consequence / status |
| --- | --- | --- |
| Non-production Moodle | Provide URL/token, install bundled plugin, grant `mod/page:view` and `local_ai_course_engine_*`, approve writes | No staging Moodle exists; draft checklist not executed — BLOCKED |
| Staging checklist | Approve and execute `docs/staging-integration-checklist.md` against a non-production Moodle only | DRAFT / NOT EXECUTED; production URL is never verification evidence |
| Production Moodle | Explicit approval + rollback plan | Currently prohibited; no live verification |
| Real AI provider | Provide key/model and spend limit | Required to measure extraction/lesson quality — BLOCKED |
| Client requirements | Approve or supply SRD/acceptance criteria | SRD/architecture/API/ERD remain empty — REQUIRES CLIENT APPROVAL |
| Client decision register | Approve all applicable entries in `docs/client-decision-register.md` | 21 decisions OPEN; no written approval recorded |
| Authentication direction | Accept app-owned portal or require Moodle-native sign-in | Draft `docs/decision-record-authentication-direction.md`; approval still required for 6.5/R53 |
| JWT lifecycle | Decide TTL, refresh/revocation/logout and storage | Draft `docs/decision-record-jwt-lifecycle.md`; 6.9 remains OPEN |
| Multi-lecturer ownership | Approve single-tenant access or require ownership | Draft `docs/decision-record-course-ownership.md`; 6.8 remains OPEN |
| Assessment/manual marking | Approve grading scope, policy and attempt workflow | Objective-only implemented; manual assessment marking not implemented. Owner direction: objective-only acceptable; written approval still required |
| Certificate policy | Approve template, signatory and branding details | Issuance/verification implemented; client presentation approval still open |
| Source textbooks | Born-digital vs scanned | Determines OCR scope; OCR implementation blocked on approval |
| CI ownership | Make `tests.yml` a required check; keep `deploy.yml` manual-only | Successful `tests.yml` run #11 verified; merge enforcement still to configure |
| Browser/a11y/load/penetration | Commission and record results | Not performed; `npm audit` also found outstanding advisories |

## 12. Deployment gate and acceptance conditions

### 12.1 Deployment gate

| Gate | Status |
| --- | --- |
| Backend full test suite | PASS — 731 passed in 59.92s (2026-11-18) |
| Frontend component tests | PASS (full vitest suite, 2026-11-18) |
| TypeScript typecheck | PASS |
| Production build | PASS |
| Python lint + compile | PASS (scoped Ruff, root Ruff, compileall) |
| Migrations single head | PASS (`f1a2b3c4d5e6`) |
| Critical journeys automated | PARTIAL (assessment/certificate unit/route + component-level; no browser E2E) |
| AuthN/authZ tests | PASS for implemented paths; ownership and JWT lifecycle decisions OPEN |
| Moodle publishing verified live | FAIL — BLOCKED BY EXTERNAL DEPENDENCY |
| Staging checklist executed | NOT EXECUTED (draft only; no staging Moodle) |
| GitHub Actions execution verified | PASS (`tests.yml` run #11, id `44271152336`, commit `3e5ec8abd8c2ec7ce84cd82e12680b332a98f04c`); required merge check not yet configured |
| Browser/a11y/load/penetration testing | NOT TESTED (no automation runtime/config; npm audit advisories outstanding) |
| Prod environment variables verified | NOT TESTED (no prod env access) |
| No open critical/high defects | FAIL (6.5, 6.8, 6.9, 6.17/D8 execution, client decisions, live/staging verification, CI failure, npm audit advisories) |
| Backup/recovery plan verified | NOT TESTED |

### 12.2 Acceptance conditions

The platform should not be accepted until at least:

1. Learner final assessment attempts, scoring, results and eligibility remain
   tested; open-ended manual marking and scoring are added or accepted as out
   of scope.
2. Certificate issuance and public verification remain tested; template,
   signatory and branding details are approved.
3. A full 16-week course is published to an approved non-production Moodle and
   read back; every section and page is verified, including Page bodies through
   `mod_page_get_pages_by_courses`.
4. A real learner enrols, opens every published lesson, completes progress,
   submits a practical task, and receives a mark.
5. A real AI provider and a real client textbook are used for one measured
   extraction/generation/QA run; truncation/fabrication controls are reviewed.
6. The Moodle-vs-portal authentication architecture is approved in writing or
   changed (draft record exists; approval is outstanding).
7. Course ownership or an explicitly accepted single-tenant model is
   documented and enforced (draft record exists; approval is outstanding).
8. Access/refresh token lifecycle, revocation and logout are resolved; Google
   registration policy is already applied to external sign-in.
9. Duplicate-title and lesson-identity handling is proven live (already
   covered by automated tests).
10. QA-gate error precedence remains pinned by tests (already covered).
11. SRD, architecture, API, and ERD documents are written and approved with
   agreed scope/acceptance evidence.
12. Authored integration/frontend CI gates are verified in GitHub Actions and
   block merges; browser E2E remains absent.
13. OCR is implemented or formally confirmed out of scope; the OCR-required
   PDF failure is already in place.
14. Production environment variables, backup, and recovery are verified.
15. `docs/staging-integration-checklist.md` is executed against an approved
   non-production Moodle only; production is never used for verification.
16. Browser, accessibility, responsive-device, load and penetration testing
   are performed and recorded, and dependency advisories are triaged with an
   approved upgrade policy.
17. Every applicable entry in `docs/client-decision-register.md` is closed with
   written owner approval, including manual assessment marking policy or its
   explicit exclusion.

## 13. Limitations and explicitly unverified items

- No production or staging Moodle read/write; no staging Moodle exists. Live
  publish, page bodies, verification and learner delivery are **BLOCKED BY
  EXTERNAL DEPENDENCY**. The staging checklist is a draft, not executed. The
  production URL `https://elearning.skillupafrica.co.ke` is never verification
  evidence.
- No real AI provider call; quality, grounding, and cost are **NOT TESTED**.
- No browser automation or manual browser session; accessibility,
  responsive-device, load and penetration testing were **NOT PERFORMED**.
- No real client textbook beyond one synthetic sample.
- No database upgrade rehearsal against a real PostgreSQL instance; only
  Alembic head inspection and test-suite database usage.
- Assessment auto-grading is limited to objective item types; open-ended
  manual marking is **NOT IMPLEMENTED**.
- JWT lifecycle, course ownership and authentication direction decision
  records are drafts, not client approvals. The wider
  `docs/client-decision-register.md` has 21 OPEN decisions and no approvals.
- CI workflows execute on GitHub. `tests.yml` run #11 is **VERIFIED** successful
  after three CI-specific dependency/environment fixes; required merge-check
  enforcement remains to be configured, and `gh` is unavailable locally.
- `npm audit` found outstanding advisories; `pip-audit` was not run because it
  is not installed.
- `docs/SRD.md`, `docs/architecture.md`, `docs/API.md` and `docs/ERD.md` remain
  empty; agreed scope and acceptance evidence is still required.
- Historical E2E results remain from the 2026-11-07 pass and are not
  re-characterized as new evidence.
- The requirements baseline is reconstructed; final acceptance criteria remain
  subject to the client's SRD.

## 14. Evidence index

| Evidence | Location |
| --- | --- |
| This audit | `docs/client-requirements-compliance-audit.md` |
| E2E result JSON (2026-11-07) | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\e2e_results.json` |
| QA-gate result JSON | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\qa_gate_result.json` |
| E2E driver | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\e2e_driver.py` |
| QA-gate driver | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\qa_gate_check.py` |
| Fake LLM | `C:\Users\ADMINI~1\AppData\Local\Temp\opencode\audit\fake_llm.py` |
| End-to-end report | `docs/end-to-end-verification-report.md` |
| Moodle integration docs | `docs/moodle-integration.md` |
| Production readiness | `docs/production-readiness.md` |
| Client decision register (21 OPEN decisions) | `docs/client-decision-register.md` |
| Historical verification | `docs/verification-report.md` |
| Role and requirement baseline | `AGENTS.md` |
| Feature/API claims | `README.md` |
| Page-body retrieval | `backend/app/services/moodle/page_content.py` |
| Lesson identity/resolution | `backend/app/services/moodle/content.py`, `lessons.py`, `mapper.py` |
| Sanitized lesson HTML | `backend/frontend/src/components/shared/SafeHtml.tsx` |
| Dependency wiring | `backend/app/core/dependencies.py` |
| Learner assessment/certificate service | `backend/app/services/learner/assessment.py` |
| Learner assessment/certificate routes | `backend/app/api/v1/learner.py`, `backend/app/api/v1/certificates.py` |
| Moodle health schema/route | `backend/app/schemas/moodle.py`, `backend/app/api/v1/moodle.py` |
| Proxy trust / external registration policy | `backend/app/services/auth/rate_limit.py`, `backend/app/services/auth/service.py` |
| OCR-required failure / analysis warnings | `backend/app/services/ingestion/text_extractor.py`, `backend/app/services/content_analysis/service.py`, `backend/app/schemas/topic.py` |
| Mocked integration tests | `backend/tests/integration/test_ingestion.py`, `test_curriculum.py`, `test_moodle.py` |
| Staging checklist (draft, not executed) | `docs/staging-integration-checklist.md` |
| JWT lifecycle decision (draft, OPEN) | `docs/decision-record-jwt-lifecycle.md` |
| Course ownership decision (draft, OPEN) | `docs/decision-record-course-ownership.md` |
| Authentication direction decision (draft, OPEN) | `docs/decision-record-authentication-direction.md` |
| CI workflows (execution verified; deploy remains manual) | `.github/workflows/tests.yml`, `.github/workflows/deploy.yml` |
| GitHub Actions successful run #11 | `https://api.github.com/repos/jecintamuhia/ai-course-engine/actions/runs/44271152336`, `.../jobs` |
| GitHub Actions failed diagnosis runs #9 and #10 | `https://api.github.com/repos/jecintamuhia/ai-course-engine/actions/runs/44269524521`, `https://api.github.com/repos/jecintamuhia/ai-course-engine/actions/runs/44269907260` |
