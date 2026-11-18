# Moodle Integration

This document describes the Moodle integration: read-level web service
client, publish pipeline, preflight readiness check, export fallback,
and the live configuration of the client site
(`https://elearning.skillupafrica.co.ke`).

For the student-facing experience — public registration, branding,
enrolment, roles, and the teacher workflow — see
[`moodle-public-access.md`](moodle-public-access.md).

## Capabilities Required

### Web service functions

All functions below must be registered for the external service token
(`MOODLE_TOKEN`).

| Function | Capability | Notes |
|---|---|---|
| `core_webservice_get_site_info` | (none) | Connectivity / version probe |
| `core_course_get_categories` | `moodle/course:view` | Category existence check |
| `core_course_get_courses_by_field` | `moodle/course:view` | Find existing course by idnumber |
| `core_course_get_contents` | `moodle/course:view` | Read sections + modules (Page **bodies are not included**) |
| `mod_page_get_pages_by_courses` | `mod/page:view` | Read published Page bodies (lesson content) |
| `core_course_create_courses` | `moodle/course:create` | Create the Moodle course |
| `core_course_update_courses` | `moodle/course:update` | Update fullname/shortname |
| `local_ai_course_engine_update_section` | `moodle/course:update` | Name/summarise a section (plugin) |
| `local_ai_course_engine_add_page` | `mod/page:addinstance` | Add a Page activity (plugin) |

The two `local_ai_course_engine_*` functions are provided by the bundled
**local Moodle plugin** (`moodle-plugin/local/ai_course_engine`). Moodle
core ships no web service that can name a course section or create an
activity instance: `core_course_edit_section`/`core_course_edit_module`
only change visibility/marker/deletion. A missing plugin function is
reported as a `content_api_unavailable` issue.

`core_course_get_contents` returns a Page module's *file* contents (a link
to the generated `index.html`), not the page body. The body is read with
the core `mod_page_get_pages_by_courses` function and merged onto the
contents before lesson rendering and post-publish verification. A token
that does not expose it is reported as `missing_capability` with
`mod/page:view`, and lesson content lookup raises a clear
`moodle_integration_error` instead of serving an empty lesson.

### Moodle configuration

| Variable | Description |
|---|---|
| `MOODLE_URL` | Base URL of the Moodle instance (e.g. `https://moodle.example.com`) |
| `MOODLE_TOKEN` | External service web service token |
| `MOODLE_COURSE_CATEGORY_ID` | Numeric id of the target course category (default: `1`) |
| `MOODLE_TIMEOUT_SECONDS` | HTTP timeout per call (default: `30.0`) |

## Architecture

```
backend/app/services/moodle/
├── client.py          # low-level WS client (httpx AsyncClient)
├── preflight.py       # readiness check (read-only, never writes)
├── mapper.py          # curriculum → Moodle course plan
├── sync.py            # idempotent publish pipeline
├── lessons.py         # lecturer-approved lesson → page renderer
├── page_content.py    # read published Page bodies (mod_page_get_pages_by_courses)
├── status.py          # status probe (legacy, kept for status endpoint)
└── export.py          # fallback curriculum export (JSON)
```

## Preflight readiness check

`GET /api/v1/moodle/preflight` returns a `MoodlePreflightResponse` with:

- `ready: bool` — True only when all functions, capabilities, and the
  target category are confirmed present
- `configured: bool` — False when `MOODLE_URL` or `MOODLE_TOKEN` are unset
- `checks: list[MoodlePreflightCheck]` — the per-item checklist. Each
  item has a `status` (`ok` / `warning` / `error`) and an honest
  `verification` method:
  - `direct` — probed against Moodle/application state
  - `inferred` — derived from an indirect observation. The Moodle Web
    Services API does **not** expose capability checks, so capabilities
    are flagged as *inferred from the declared web service functions*,
    not claimed as verified.
  - `not_verifiable` — cannot be confirmed through the API (e.g. checks
    that cannot run because the connection/authentication failed)
- `issues` / `blocking_issues` (aliases) — list of blockers, each with
  `kind`, `message`, `ws_function`, `capability`, and `admin_action`
  (human-readable instructions for the Moodle admin)
- `category_found: bool` — whether the target category id is visible
  to the token

Checklist items (in order): connection & API access, token
authentication, course category, one item per required web service
function (direct), and one item per required capability (inferred).

**Issue kinds**: `not_configured`, `invalid_parameter`, `invalid_token`,
`auth_failure`, `missing_capability`, `unsupported_function`,
`content_api_unavailable` (missing local plugin function),
`invalid_category`, `transient_failure`

The check is entirely read-only — it never creates or modifies courses,
sections, or modules. It uses `httpx.ConnectError`, HTTP 403,
`invalidtoken` error codes, and timeout detection to classify
connectivity failures as actionable issue kinds. An `accessexception`
on the site-info handshake (function registered but not exposed to the
token's service) is reported as `missing_capability` with the list of
functions the admin must add to the service.

## Status and deep check

`GET /api/v1/moodle/status` is the permissive liveness view:
`connected=true` means the Moodle site-info probe succeeded.

`GET /api/v1/moodle/check` adds a category-visibility probe without
collapsing the two signals. It returns `connected`, `ready`, and
`degraded`:

- `connected=false` means the site/token probe failed.
- `connected=true, degraded=true, ready=false` means Moodle answered, but
  the configured `MOODLE_COURSE_CATEGORY_ID` is not visible to the token.
  The error says publishing would fail rather than claiming Moodle is down.
- `connected=true, ready=true` means both probes passed.

This is a read-only check. No live Moodle run is claimed for the current
remediation pass; the production URL is never verification evidence.

## Publish pipeline

`POST /api/v1/moodle/publish` triggers `MoodleSyncService.publish_curriculum`.

### Flow

1. Curriculum must be in `APPROVED` or `PUBLISHED` status
2. **Preflight gate** — `run_readiness_check` blocks if any issue exists
   (raises `MoodlePublishBlockedError` = HTTP 409 with full issue details;
   curriculum remains APPROVED)
3. Build `MoodleCoursePlan` via the mapper (fullname, shortname, idnumber,
   weekly sections, and lesson pages):
   - the course **fullname** is the curriculum title (a title shaped
     like a UUID is an internal id, never a human name, and falls back
     to `AI-Generated Course`)
   - the **shortname** is derived deterministically from the title
     (lower-cased ASCII slug) plus the last 8 hex chars of the
     curriculum id tail as a stability/uniqueness suffix; the full UUID
     and the `ai-ece-` idnumber prefix never appear in the visible
     names, but the UUID remains the course **idnumber**
   - each week becomes **exactly one section** named after the week; no
     dedicated page is generated for a week (the section itself
     represents the week)
4. **Lesson pages** — APPROVED lessons for the curriculum are rendered to
   HTML (see [`lessons.py`](../backend/app/services/moodle/lessons.py)) and
   attached to the plan as lesson pages. Each weekly section in the plan
   can carry zero or more lesson pages; if no lessons are approved the plan
   is byte-identical to the previous behavior
5. Find existing Moodle course by idnumber (`core_course_get_courses_by_field`)
   or create (`core_course_create_courses`); `create_courses` also
   pre-creates the weekly sections via `numsections=N`
6. Sync sections: upsert each weekly section's name/summary by section
   *number* via `local_ai_course_engine_update_section` (the plugin
   creates a missing section, so no separate create/update branch exists)
7. Sync lesson pages: add a `Page` activity per lesson when a page with
   the same name is not already present in that section, via
   `local_ai_course_engine_add_page`. Publishing is idempotent by page
   name per section, so a publish must be re-run after lecturer review
   approves new lessons. Lessons whose rendered content is byte-identical
   are published only once, so duplicated curriculum/lesson items never
   create duplicate pages; two genuinely different lessons that share a
   title are both published
8. **Post-publish verification** — read back course contents, merge Page
   bodies via `mod_page_get_pages_by_courses`, and assert every planned
   section and its lesson pages are present (verification applies the same
   content-dedup rule as sync)
9. If verified: status = `PUBLISHED`, record persisted as `SYNCED`
10. If NOT verified: status stays `APPROVED`, a `SYNC_FAILED` record is
    persisted (with moodle_course_id and idnumber so retries resume
    without duplicates), and `MoodleIntegrationError` is raised
11. **Idempotency** — re-publishing a partially-synced course reuses the
    existing Moodle course, always re-names the sections in place, and
    adds only missing lesson pages. Once a lesson page exists it is never
    modified (the engine never updates course content)

### Error semantics

| HTTP | Error code | Meaning |
|---|---|---|
| 409 | `moodle_publish_blocked` | Preflight failed; Moodle is not ready. Check `issues` for admin actions. |
| 400 | `invalid_curriculum_status` | Curriculum must be APPROVED or PUBLISHED |
| 502 | `moodle_integration_error` | Moodle rejected the call, is unreachable, or post-publish verification failed |

All Moodle HTTP/timeout errors are wrapped in `MoodleIntegrationError`
with `recoverable: True` and the original function name in `details`.

## Export fallback

`GET /api/v1/moodle/publish/.../export` (currently
`GET /api/v1/curricula/{id}/export`) returns a JSON export suitable as
a reference document for a Moodle administrator to import manually.

- Format: `ai-course-engine/curriculum-export`, version 1
- `importable: false` — the engine never claims this can be directly
  imported into Moodle without admin assistance
- Content: weeks with topics, learning objectives, prerequisites,
  difficulty, workload, source provenance

This is a read-only endpoint with no side effects on the Moodle instance.

## Frontend Publish panel

The `MoodlePublishPanel` component (in
`frontend/src/components/moodle/MoodlePublishPanel.tsx`) displays:

- **Readiness card**: green (ready), amber (blocked with issue list
  showing kind badge, capability, ws_function, admin_action), or
  could-not-check state
- **Publish button**: disabled unless preflight is ready
- **Export download button**: downloads the JSON export as a `.json` file
  for the Moodle administrator
- **Re-check button**: re-runs the preflight without a page reload

## Live configuration (historical evidence only)

The facts below were verified against the live client site in an earlier pass.
They are not execution evidence for the current remediation pass, and the
production URL must not be used as a staging target. Verified against the live client site
(`https://elearning.skillupafrica.co.ke`, Moodle **4.3.12**, site name
**Skillup Action Africa**):

- Token user: `skillupadmin`
- The token's external service must expose the full set of functions the
  publisher needs: `core_webservice_get_site_info`,
  `core_course_get_categories`, `core_course_get_courses_by_field`,
  `core_course_get_contents`, `mod_page_get_pages_by_courses`,
  `core_course_create_courses`, `core_course_update_courses`, and the two
  bundled plugin functions `local_ai_course_engine_update_section` and
  `local_ai_course_engine_add_page`.
- The last recorded live check (`GET /api/v1/moodle/preflight` returning
  `ready: true`) predates the Page-body requirement. Re-run preflight on
  the site: the token must also expose `mod_page_get_pages_by_courses`
  (`mod/page:view`) before lesson content can be read back.
- Published course id **5** (`idnumber ai-ece-643a805c-…`) belongs to
  curriculum `643a805c-050d-4910-bf2d-97da7ef68dfb`. It currently
  contains 17 sections (General + Week 1–16) but only **Week 1** has
  page resources, so it must be re-published to deliver the complete
  16-week content.

The two `local_ai_course_engine_*` functions are provided by the bundled
**local Moodle plugin** (`moodle-plugin/local/ai_course_engine`), which
must remain installed on the site:
- `local_ai_course_engine_update_section` — `moodle/course:update`
- `local_ai_course_engine_add_page` — `mod/page:addinstance`

Moodle core ships no web service that can name a course section or
create an activity instance; the plugin exists for exactly that reason
and is required for publishing. Keep it installed and up to date when
the plugin repository changes.

Student-facing configuration (registration, enrolment, branding, roles)
is tracked in [`moodle-public-access.md`](moodle-public-access.md).

## Migrations

No database migrations are required. The `courses` table already
includes `moodle_course_id`, `moodle_url`, `idnumber`, `status`
(SYNCED/SYNC_FAILED), `sync_error`, `last_sync_at`,
`sections_published`, and `resources_published` columns.

## Tests

| Test file | Covers |
|---|---|
| `test_moodle_preflight.py` | All issue kinds (incl. `content_api_unavailable`), classification (incl. `accessexception`), category probe, plain-string functions, readiness checklist items + verification method |
| `test_moodle_export.py` | Export structure, importable flag, fields, provenance |
| `test_moodle_sync.py` | Preflight gate, verification gate, idempotent retry, partial persistence, overrides, section upsert-by-number |
| `test_moodle_api.py` | API routes for status, preflight, and the degraded `/check` response when category probing fails |
| `test_moodle_client.py` | HTTP client edge cases, plugin section/page function calls, Page-body read |
| `test_moodle_content.py` | Lesson content resolution: marker, computed name, legacy title, content equality, missing body |
| `test_moodle_mapper.py` | Plan building (unchanged) and page-name disambiguation |
| `backend/tests/integration/test_moodle.py` | Mocked end-to-end page-body mapping and missing-body errors (no live Moodle) |
