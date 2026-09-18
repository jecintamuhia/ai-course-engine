# Moodle Integration

This document describes the Moodle integration: read-level web service
client, publish pipeline, preflight readiness check, export fallback,
and the current live-publish blocker.

## Capabilities Required

### Web service functions

All functions below must be registered for the external service token
(`MOODLE_TOKEN`).

| Function | Capability | Notes |
|---|---|---|
| `core_webservice_get_site_info` | (none) | Connectivity / version probe |
| `core_course_get_categories` | `moodle/course:view` | Category existence check |
| `core_course_get_courses_by_field` | `moodle/course:view` | Find existing course by idnumber |
| `core_course_get_contents` | `moodle/course:view` | Read sections + modules |
| `core_course_create_courses` | `moodle/course:create` | **BLOCKED** — currently missing |
| `core_course_update_courses` | `moodle/course:update` | Update fullname/shortname |
| `core_course_create_sections` | `moodle/course:update` | Moodle 4.0+ only |
| `core_course_update_sections` | `moodle/course:update` | Section name sync |
| `mod_page_add_instance` | `mod/page:addinstance` | Create page modules |

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
├── __init__.py
├── client.py          # low-level WS client (httpx AsyncClient)
├── preflight.py       # readiness check (read-only, never writes)
├── mapper.py          # curriculum → Moodle course plan
├── sync.py            # idempotent publish pipeline
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
`invalid_category`, `transient_failure`

The check is entirely read-only — it never creates or modifies courses,
sections, or modules. It uses `httpx.ConnectError`, HTTP 403,
`invalidtoken` error codes, and timeout detection to classify
connectivity failures as actionable issue kinds.

## Publish pipeline

`POST /api/v1/moodle/publish` triggers `MoodleSyncService.publish_curriculum`.

### Flow

1. Curriculum must be in `APPROVED` status
2. **Preflight gate** — `run_readiness_check` blocks if any issue exists
   (raises `MoodlePublishBlockedError` = HTTP 409 with full issue details;
   curriculum remains APPROVED)
3. Build `MoodleCoursePlan` via the mapper (title, fullname, shortname,
   idnumber, sections with page modules and section names)
4. Find existing Moodle course by idnumber (`core_course_get_courses_by_field`)
   or create (`core_course_create_courses`)
5. Sync sections: create missing sections, update existing section names
   via `core_course_update_sections`
6. Sync page modules: update existing page content or add new pages via
   `mod_page_add_instance`
7. **Post-publish verification** — read back course contents and assert
   all planned sections and page modules are present
8. If verified: status = `PUBLISHED`, record persisted as `SYNCED`
9. If NOT verified: status stays `APPROVED`, a `SYNC_FAILED` record is
   persisted (with moodle_course_id and idnumber so retries resume
   without duplicates), and `MoodleIntegrationError` is raised
10. **Idempotency** — re-publishing a partially-synced course reuses the
    existing Moodle course, skips sections that already exist, and adds
    only missing page modules

### Error semantics

| HTTP | Error code | Meaning |
|---|---|---|
| 409 | `moodle_publish_blocked` | Preflight failed; Moodle is not ready. Check `issues` for admin actions. |
| 400 | `invalid_curriculum_status` | Curriculum must be APPROVED |
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

## Current blocker

Configuration verified against the live client site
(`https://elearning.skillupafrica.co.ke`, Moodle **4.3.12**):

- Token user: `skillupadmin`
- Category `1` exists and is visible to the token (auth + connection OK);
  read-level functions are exposed
- The token's external web service declares **none of the write
  functions** required for publishing — all five are missing from the
  exposed service:

| Operation | Web service function | Capability required |
|---|---|---|
| Course creation | `core_course_create_courses` | `moodle/course:create` |
| Course update | `core_course_update_courses` | `moodle/course:update` |
| Section creation | `core_course_create_sections` | `moodle/course:update` |
| Section update | `core_course_update_sections` | `moodle/course:update` |
| Resource creation | `mod_page_add_instance` | `mod/page:addinstance` |

This is visible in the preflight response:

```json
{
  "ready": false,
  "checks": [
    { "label": "Moodle connection & API access", "status": "ok", "verification": "direct" },
    { "label": "Web service token authentication", "status": "ok", "verification": "direct" },
    { "label": "Course category", "status": "ok", "verification": "direct" },
    { "label": "Web service function core_course_create_courses", "status": "error", "verification": "direct" },
    { "label": "Capability moodle/course:create", "status": "error", "verification": "inferred" },
    "..."
  ],
  "blocking_issues": [
    {
      "kind": "missing_capability",
      "message": "core_course_create_courses is not exposed to the configured web service token. Create the Moodle course on first publish.",
      "ws_function": "core_course_create_courses",
      "capability": "moodle/course:create",
      "admin_action": "In Moodle: Site administration \u2192 Plugins \u2192 Web services \u2192 External services, add the required functions to the token's service, and grant the capabilities listed for it. Required capability: moodle/course:create."
    }
  ]
}
```

### What the Moodle administrator must do

1. In Site administration → Plugins → Web services → External services,
   open the service bound to the `skillupadmin` token
2. Add the five write functions: `core_course_create_courses`,
   `core_course_update_courses`, `core_course_create_sections`,
   `core_course_update_sections`, `mod_page_add_instance`
3. Grant (or allow auto-grant via "capabilities of the service" role)
   `moodle/course:create`, `moodle/course:update`, `mod/page:addinstance`,
   and `moodle/course:view`
4. Run `GET /api/v1/moodle/preflight` to confirm `ready: true` and every
   check is `ok`
5. Test publishing with a small curriculum into a test course/category
   (category `1` is verified reachable) and confirm the post-publish
   verification succeeds

Live publishing must NOT be attempted or claimed successful until the
admin adds the functions and the preflight returns ready.

## Migrations

No database migrations are required. The `courses` table already
includes `moodle_course_id`, `moodle_url`, `idnumber`, `status`
(SYNCED/SYNC_FAILED), `sync_error`, `last_sync_at`,
`sections_published`, and `resources_published` columns.

## Tests

| Test file | Covers |
|---|---|
| `test_moodle_preflight.py` | All issue kinds, classification, category probe, plain-string functions, readiness checklist items + verification method |
| `test_moodle_export.py` | Export structure, importable flag, fields, provenance |
| `test_moodle_sync.py` | Preflight gate, verification gate, idempotent retry, partial persistence, overrides |
| `test_moodle_api.py` | API routes for status and preflight |
| `test_moodle_client.py` | HTTP client edge cases (unchanged) |
| `test_moodle_mapper.py` | Plan building (unchanged) |
