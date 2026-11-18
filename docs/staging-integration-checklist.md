# Staging Moodle Integration Checklist

**Status:** DRAFT / NOT EXECUTED. No staging or production Moodle instance has
been supplied or exercised here, and no publish, enrolment or learner write has
been performed. Historical notes in `docs/moodle-integration.md` are not
execution evidence for this checklist. Staging use and any Moodle writes require
separate owner authorisation; none is claimed here.

Use this checklist only after a **non-production** Moodle URL, web-service
token, target category id and disposable test data are supplied. Do not point it
at production or at a site whose ownership is unclear. Record API paths,
curriculum/course ids, timestamps and `X-Request-ID` values; never record
tokens. All product/architecture decisions referenced here remain pending
client approval.

Paths below are exact. Replace `{curriculum_id}`, `{course_id}`, `{lesson_id}`,
`{block_id}`, `{submission_id}` and `{reference}` with real ids. Staff calls
need `Authorization: Bearer <staff token>`; learner calls need a learner token.
`GET /api/v1/certificates/verify/{reference}` is public.

## 1. Preconditions

| Input / condition | Required |
| --- | --- |
| Staging Moodle | `MOODLE_URL`, `MOODLE_TOKEN`, `MOODLE_COURSE_CATEGORY_ID`; `MOODLE_TIMEOUT_SECONDS` if non-default |
| Plugin | `moodle-plugin/local/ai_course_engine` installed; both `local_ai_course_engine_*` functions exposed to the token |
| Data | One reviewed/approved curriculum, one staff account and one test learner account; no production data |
| Safety | Rollback/cleanup plan for the staging course; explicit permission to write to that staging site |

**STOP** if any input is missing, points to production, or the token/category
owner is unknown.

## 2. Read-only checks first — no Moodle writes

| # | Check | API | Expected | STOP if |
| --- | --- | --- | --- | --- |
| 1 | Application readiness | `GET /health/ready` | 200, `status: ready` | 503 or any `not_ready` field |
| 2 | API liveness | `GET /api/v1/health` | 200, `status: ok` | Non-200 |
| 3 | Staff sign-in | `POST /api/v1/auth/login` | 200 with `access_token`, `redirect_to: /dashboard` | Non-200, staff role absent, or unexpected destination |
| 4 | Moodle status | `GET /api/v1/moodle/status` | `configured: true`, `connected: true` | `configured: false`, `connected: false`, or error text |
| 5 | Moodle health | `GET /api/v1/moodle/check` | `connected: true`, `default_category_found: true`, `degraded: false` | `degraded: true`, missing category, or error |
| 6 | Moodle preflight | `GET /api/v1/moodle/preflight` | `ready: true`, `configured: true`, `category_found: true`, no `blocking_issues` | `ready: false` or any blocking issue |
| 7 | QA report | `GET /api/v1/curricula/{curriculum_id}/quality-report` | Latest report present and not `fail` | Missing report or verdict `fail` |
| 8 | Coverage | `GET /api/v1/curricula/{curriculum_id}/coverage` | 200; coverage report available | Non-200 or unexplained gaps |
| 9 | Export fallback | `GET /api/v1/curricula/{curriculum_id}/export` | 200, `importable: false` | Non-200 or misleading importability claim |
| 10 | Baseline courses | `GET /api/v1/courses` | Recorded list; intended `idnumber` not unexpectedly in use | Conflict with an existing `idnumber` unless re-publish is intended |

Preflight must show all nine functions required by the current implementation:
`core_webservice_get_site_info`, `core_course_get_categories`,
`core_course_get_courses_by_field`, `core_course_get_contents`,
`mod_page_get_pages_by_courses`, `core_course_create_courses`,
`core_course_update_courses`, `local_ai_course_engine_update_section`, and
`local_ai_course_engine_add_page`. Function checks are direct; capability
checks are **inferred** from declared functions and are not proof of effective
Moodle permissions. `mod_page_get_pages_by_courses` is required for lesson
bodies (`mod/page:view`); a missing plugin function is reported as
`content_api_unavailable`.

**STOP** on `not_configured`, `invalid_token`, `auth_failure`,
`missing_capability`, `unsupported_function`, `content_api_unavailable`,
`invalid_category` or `transient_failure`. Do not publish to "see if it works".

## 3. Publish — first Moodle write

Curriculum must be `APPROVED` or `PUBLISHED` and must have passed the read-only
gate above.

| Action | API | Expected | STOP if |
| --- | --- | --- | --- |
| Publish | `POST /api/v1/moodle/publish/{curriculum_id}` | 200 with `course_id`, `moodle_course_id`, `idnumber`, `created`, `sections_published`, `resources_published`, `verified: true` | Any error below, `verified: false`, or missing `moodle_course_id` |
| 400 | same | — | `invalid_curriculum_status`: curriculum is not publishable |
| 409 | same | — | `qa_blocked` or `moodle_publish_blocked`; no Moodle write should have occurred |
| 502 | same | — | `moodle_integration_error` (Moodle rejected/failed verification) |

Optional request fields are `idnumber`, `fullname`, `shortname` and
`category_id`. The engine finds or creates by `idnumber`; it names weekly
sections, adds missing lesson pages, and **does not update existing page
bodies**. Re-publishing is idempotent for pages but is still a write.

**STOP** after a failure. Record the response and course record state before
re-running; do not blindly retry. For a 16-week curriculum expect `General`
plus Week 1–16 sections according to the mapper.

## 4. Verify and read back — no new Moodle writes

| # | Check | API | Expected | STOP if |
| --- | --- | --- | --- | --- |
| 1 | Coarse presence | `POST /api/v1/moodle/verify/{course_id}` | `found: true`, stored `moodle_course_id`, plausible section/module counts and names | `found: false`, error, or counts inconsistent with the publish response |
| 2 | Stored record | `GET /api/v1/courses/{course_id}` | `status: synced`, `moodle_course_id`, `last_sync_at`, no `sync_error` | `status: sync_failed` or empty publication metadata |
| 3 | Staff structure | `GET /api/v1/lecturer/courses/{course_id}/content` | All weekly sections and page modules with resolved internal `lesson_id` values | Missing sections/modules, unresolved lesson ids, or integration error |
| 4 | Staff lesson bodies | `GET /api/v1/lecturer/courses/{course_id}/lessons/{lesson_id}/content` | Non-empty HTML for each lesson; marker resolves to the requested lesson | 404, `moodle_integration_error`, empty body, or wrong-lesson content |

`POST /api/v1/moodle/verify/{course_id}` is a read-only endpoint despite its
HTTP method: it reports section/module counts only. It does **not** prove Page
bodies are correct. Body verification depends on
`mod_page_get_pages_by_courses` and the per-lesson reads above.

## 5. Learner flow

Use a fresh test learner. Self-registration always creates `student`.

| # | Step | API | Expected | STOP if |
| --- | --- | --- | --- | --- |
| 1 | Register | `POST /api/v1/auth/register` | 201, role `student`, server-supplied `redirect_to` (`/learn` by default) | Staff role, missing `redirect_to`, or non-201 |
| 2 | Profile | `GET /api/v1/learner/profile` | 200, caller's own profile | 401/403 or another user's data |
| 3 | Catalogue | `GET /api/v1/learner/catalog` | Published staging course visible | Course absent or staff-only route reachable |
| 4 | Enrol | `POST /api/v1/learner/courses/{course_id}/enrol` | `enrolled: true`, `enrolment_id` | Non-200 or enrolment not recorded |
| 5 | Course detail | `GET /api/v1/learner/courses/{course_id}` | `enrolled: true`, lessons, milestones and progress | 401/403/404 or another learner's records |
| 6 | Structure | `GET /api/v1/learner/courses/{course_id}/content` | Sections/modules with internal `lesson_id` values | Unresolved lesson ids or Moodle read error |
| 7 | Lesson content | `GET /api/v1/learner/courses/{course_id}/lessons/{lesson_id}/content` | Non-empty HTML for **every** lesson, matching that `lesson_id`; rendered through `SafeHtml` | Empty body, 404, integration error, script/handler markup surviving render, or wrong lesson |
| 8 | Completion | `POST /api/v1/learner/courses/{course_id}/lessons/{lesson_id}/complete` | `completed: true`, `milestone_id`; progress increments | No milestone or progress does not change |
| 9 | Hand-in | `POST /api/v1/learner/courses/{course_id}/blocks/{block_id}/submit` | `submission` returned with caller/user scope | Non-200 or wrong ownership |
| 10 | Learner submissions | `GET /api/v1/learner/submissions` | Only this learner's submissions | Missing or foreign records |
| 11 | Staff review | `GET /api/v1/lecturer/courses/{course_id}/submissions/pending`, then `POST /api/v1/lecturer/submissions/{submission_id}/grade` or `/return` | The staged submission is visible, graded/returned and attributed | Missing submission, 403 for staff, or wrong grade/feedback |
| 12 | Final assessment | `GET /api/v1/learner/courses/{course_id}/final-assessment` | Sanitised questions, no answers, configured pass percent | Questions expose answers or endpoint unavailable |
| 13 | Attempt | `POST /api/v1/learner/courses/{course_id}/final-assessment/attempts` | Stored `AssessmentAttemptRead` with score and `passed` | Rejected with no auto-gradable items, wrong score, or duplicate attempt number |
| 14 | Attempt history | `GET /api/v1/learner/courses/{course_id}/final-assessment/attempts` | Only the caller's attempts | Missing or foreign attempts |
| 15 | Certificate | `POST /api/v1/learner/courses/{course_id}/certificate`, then `GET /api/v1/learner/certificates` | Issued once when all lessons are complete and a passing attempt exists | Issued below the configured pass percent, duplicate, or issued without eligibility |
| 16 | Public verification | `GET /api/v1/certificates/verify/{reference}` | Snapshotted learner/course/score/date match the certificate | Reference not found or data mismatch |

Objective final-assessment items are auto-graded; open-ended item types are
preserved as feedback but excluded from the score. Stop if that limitation is
unexpected for the test assessment.

## 6. Outcome record

Record `ready` / `verified` / `found` flags, expected versus observed section
and page counts, resolved lesson ids, learner progress, attempt and certificate
references, and every stop condition encountered. Treat the result as staging
evidence only. Production publishing, client acceptance and all architecture
decisions remain separate, unapproved gates.
