# AI Course Engine

Production-oriented platform for AI-assisted educational content ingestion, knowledge extraction, curriculum planning, lecturer review, and Moodle publishing.

## Current status

A working MVP covering the end-to-end flow:

1. **Upload** a PDF textbook
2. **Ingestion** — extract text, detect chapter/section structure, chunk into semantic segments (background worker). Re-detecting a structure re-links existing chunks by page number instead of orphaning them, and an analysis that yields no topics fails the job rather than reporting success
3. **AI analysis** — extract topics, concepts, and *within-chapter* prerequisites via LLM (one call per chapter)
4. **Topic canonicalization** — assign every topic a stable normalized identity and importance, and merge *safe* exact-normalized-title duplicates into a canonical topic with aliases (nothing deleted; near-duplicates are surfaced for review, never auto-collapsed)
5. **Dependency resolution** — a document-wide linking pass sees every real topic title at once and resolves *cross-chapter* prerequisites, which per-chapter extraction cannot do because the other chapters' topics do not exist yet. Its proposals are merged with the within-chapter links, then topologically ordered. Unknown, ambiguous, self-referential, forward-pointing, and cycle-causing edges are rejected and reported, never guessed
6. **Curriculum generation** — deterministic weekly planner (16 weeks by default, configurable) that always spans exactly the requested number of weeks, spreads topics across the full horizon within workload budgets, and carries per-week learning objectives
7. **Course content generation** — LLM-generated, source-grounded lessons per week (text, diagrams, knowledge checks, activities, resources, videos) with per-block provenance and source maps
8. **Assessment generation** — weekly-unit and course-final assessments aligned to learning objectives and grounded in the unit's textbook chunks (items validated structurally, objective → lesson → evidence mapping persisted)
9. **Automated content QA** — a gates approval and Moodle publishing: checks coverage, duplication, provenance, content depth, learning design, and Moodle readiness, persists a per-version report, and produces a textbook coverage report
10. **Lecturer review** — submit-for-review / approve / reject workflow for curricula, lessons (per-block and whole-lesson) and content blocks (content-QA must pass before approval)
11. **Moodle publish** — idempotent course creation with weekly sections (one per week, no duplicate weekly-page resources) and APPROVED lessons as lesson pages; verify after publish
12. **Web UI** — same-origin SPA served by FastAPI; sidebar navigation across all screens

**Current limitation:** AI analysis (step 3) requires a running LLM. The provider architecture supports OpenRouter (production default) and OpenAI. Production uses OpenRouter's API with structured outputs; each chapter's extraction completes quickly using a bounded per-chapter context (~6000 chars) and a compact schema to keep requests small. The prompt spells out the nested shape (each concept is an object with `name`/`description`), and schema violations are retried with the corrected schema; header-only/TOC pages whose text is shorter than `AI_MIN_CONTENT_CHARS` are skipped without an LLM call. Transient failures (rate limits, provider overload, timeouts) are retried with bounded exponential backoff; permanent errors (invalid key, insufficient credits) fail fast. Lesson generation (step 6) reuses the same provider configuration and never fabricates content — see [`docs/course-content.md`](docs/course-content.md).

## Tech stack

- Python 3.12+, FastAPI, Pydantic v2
- SQLAlchemy 2.x (async), PostgreSQL 17, Alembic
- Redis queue drained by a native asyncio worker (no rq/Celery)
- Docker Compose (api, worker, postgres, redis)
- React + TypeScript SPA served by FastAPI (`backend/frontend/`)
- LLM providers abstracted behind `LLMProvider` (`app/services/ai/base.py`); OpenRouter is the production default; OpenAI available as an opt-in
- Moodle web service API integration

## Quick start

```bash
# Start all services (API, worker, PostgreSQL, Redis)
cd backend
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Open the web UI
# http://localhost:8000
```

The API serves the frontend SPA from `backend/frontend/` at the root path.

### Running the CLI demo

```bash
# Full pipeline demo (stops before Moodle publish)
cd backend
python ../scripts/run_demo.py

# Include Moodle publish (requires MOODLE_URL/MOODLE_TOKEN in backend/.env)
python ../scripts/run_demo.py --publish

# Course-content demo: generate/review/publish one week's lessons for an
# existing APPROVED curriculum (see docs/course-content.md). Run from
# backend/ so .env loads, overriding DATABASE_URL to reach the
# Docker-published Postgres from the host.
cd backend
$env:DATABASE_URL="postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine"
.venv\Scripts\python scripts\demo_course_content.py --week 1
```

## Configuration

All configuration is environment-driven via `backend/.env` (git-ignored).

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | `postgresql+asyncpg://...` |
| `REDIS_URL` | Yes | — | `redis://redis:6379/0` |
| `AI_PROVIDER` | No | `openrouter` | `openrouter` (production) or `openai` (optional) |
| `OPENAI_API_KEY` | opt-in | — | Required when `AI_PROVIDER=openai` |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model name |
| `OPENROUTER_API_KEY` | Yes | — | OpenRouter API key (`sk-or-...`); required when `AI_PROVIDER=openrouter` |
| `OPENROUTER_MODEL` | Yes | — | OpenRouter model id, e.g. `openai/gpt-4o` |
| `OPENROUTER_BASE_URL` | No | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `OPENROUTER_TIMEOUT_SECONDS` | No | `300` | Per-request timeout |
| `OPENROUTER_MAX_ATTEMPTS` | No | `3` | Schema-correction attempts for structured output |
| `OPENROUTER_MAX_RETRIES` | No | `5` | Bounded retries for transient failures (429/5xx/network) |
| `OPENROUTER_RETRY_BASE_DELAY_SECONDS` | No | `2.0` | Initial backoff between retries (doubles each attempt) |
| `OPENROUTER_MAX_RETRY_DELAY_SECONDS` | No | `120.0` | Upper bound on any single retry wait |
| `AI_EXTRACT_TEMPERATURE` | No | `0` | Sampling temperature for extraction calls |
| `AI_EXTRACT_MAX_TOKENS` | No | `2560` | Output token budget per extraction call |
| `AI_EXTRACT_MAX_TOPICS` | No | `6` | Max topics requested per chapter |
| `AI_EXTRACT_MAX_OBJECTIVES` | No | `3` | Max learning objectives per topic |
| `AI_EXTRACT_MAX_CONCEPTS` | No | `3` | Max concepts per topic |
| `AI_EXTRACT_MAX_PREREQUISITES` | No | `2` | Max prerequisite topics per topic |
| `AI_MAX_CONTEXT_CHARS` | No | `6000` | Per-chapter text cap sent to the LLM (chunks beyond it are omitted, never fabricated) |
| `AI_MIN_CONTENT_CHARS` | No | `500` | Chapters with bounded text shorter than this are skipped without an LLM call (header-only/TOC pages) |
| `MOODLE_URL` | No | — | Moodle instance URL |
| `MOODLE_TOKEN` | No | — | Moodle web service token |
| `MOODLE_COURSE_CATEGORY_ID` | No | `1` | Default Moodle course category |

See `.env.example` for the full list.

See `.env.example` for the full list.

## API endpoints

All routes are under `/api/v1`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/dashboard` | Aggregate stats (documents, curricula, courses, Moodle status) |
| `POST` | `/documents` | Upload a textbook (multipart/form-data) |
| `GET` | `/documents` | List all documents with processing counts |
| `GET` | `/documents/{id}` | Single document metadata |
| `GET` | `/documents/{id}/overview` | Document + processing summary |
| `POST` | `/documents/{id}/extract` | Extract text pages |
| `POST` | `/documents/{id}/detect-structure` | Detect chapters/sections |
| `POST` | `/documents/{id}/chunk` | Create semantic chunks |
| `POST` | `/documents/{id}/analyze` | AI topic/concept extraction (LLM) |
| `POST` | `/documents/{id}/dependencies` | Resolve prerequisite graph |
| `GET` | `/documents/{id}/topics` | Extracted topics |
| `POST` | `/ingestion/jobs` | Start background processing job |
| `GET` | `/ingestion/jobs/{id}` | Job status |
| `POST` | `/ingestion/jobs/{id}/cancel` | Cancel a running job |
| `POST` | `/curricula` | Generate a weekly curriculum |
| `GET` | `/curricula?document_id=...` | List curricula for a document |
| `GET` | `/curricula/{id}` | Curriculum detail with units + reviews |
| `POST` | `/curricula/{id}/submit-for-review` | Move to lecturer review queue (content QA must pass) |
| `POST` | `/curricula/{id}/review` | Record approve/reject decision |
| `POST` | `/curricula/{id}/canonicalize` | Run safe topic canonicalization + dedup |
| `POST` | `/curricula/{id}/qa` | Run content QA; returns persisted report + whether publishing is blocked |
| `GET` | `/curricula/{id}/quality-report` | Latest QA report for a curriculum |
| `GET` | `/curricula/{id}/coverage-report` | Textbook coverage report (topics → lessons/resources/videos) |
| `POST` | `/curricula/{id}/assessments/generate` | Generate a course-final assessment (LLM) |
| `POST` | `/curricula/{id}/units/{unit_id}/assessments/generate` | Generate a weekly-unit assessment (LLM) |
| `GET` | `/curricula/{id}/assessments` | List a curriculum's assessments |
| `GET` | `/curricula/{id}/units/{unit_id}/assessments` | List a unit's assessments |
| `GET` | `/assessments/{id}` | Single assessment with items, alignment, markers |
| `POST` | `/assessments/{id}/review` | Approve/reject an assessment |
| `GET` | `/courses` | Published Moodle courses |
| `GET` | `/moodle/status` | Moodle connection status (permissive) |
| `GET` | `/moodle/check` | Deep Moodle health check (read-only) |
| `POST` | `/moodle/publish/{curriculum_id}` | Publish approved curriculum (incl. APPROVED lessons as pages) to Moodle |
| `POST` | `/moodle/verify/{course_id}` | Verify course exists in Moodle |
| `POST` | `/course-content/weeks/{unit_id}/generate` | Generate lessons for a weekly unit (LLM) |
| `GET` | `/course-content/weeks/{unit_id}/lessons` | List a week's lessons with statuses |
| `GET` | `/course-content/lessons/{lesson_id}` | Lesson detail with content blocks |
| `GET` | `/course-content/lessons/{lesson_id}/source-map` | Block → source provenance map |
| `POST` | `/course-content/lessons/{lesson_id}/submit-for-review` | Move lesson to the review queue |
| `POST` | `/course-content/lessons/{lesson_id}/review` | Approve/reject a lesson |
| `POST` | `/course-content/blocks/{block_id}/review` | Approve/reject/comment one content block |
| `POST` | `/course-content/blocks/{block_id}/regenerate` | Regenerate a rejected block |
| `DELETE` | `/course-content/blocks/{block_id}` | Delete a content block |

## Authentication

All `/api/v1` business endpoints require a valid access token. Public endpoints are
`GET /health`, `POST /api/v1/auth/login`, `GET /api/v1/auth/methods` and — when
Google sign-in is configured — `GET /api/v1/auth/google/start`. The SPA redirects
unauthenticated visitors to `/login`.

Authentication uses user accounts with JWT bearer tokens:

- Passwords are hashed with **Argon2** (`pwdlib`) and never stored in plain text.
- Tokens are HS256-signed with `SECRET_KEY` and expire after
  `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 720 minutes = 12 h).
- Roles: `admin` (full control, can create users) and `lecturer` (review/publish).

To create the first admin (or lecturer) account, run the bootstrap script inside
the API container or locally against the database:

```bash
python backend/scripts/create_admin.py --email admin@example.com --full-name "Admin User" --role admin
```

The script prompts for a password on stdin (or accepts `--password`). Never pass
real passwords on the command line or store them in the repository.

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Public. Exchange email + password for an access token |
| `GET` | `/auth/methods` | Public. Which sign-in methods are currently available |
| `POST` | `/auth/register` | Public. Self-register as a lecturer and receive a token |
| `GET` | `/auth/google/start` | Public. Begin the Google authorization-code flow |
| `GET` | `/auth/google/callback` | Public. Google redirect target; returns a one-time code |
| `POST` | `/auth/google/exchange` | Public. Trade the one-time code for an access token |
| `GET` | `/auth/me` | Current authenticated user profile |
| `POST` | `/auth/users` | Admin-only. Create a user |

### Self-registration

Lecturers can create their own accounts at `/register`; the server exposes this as
`POST /api/v1/auth/register`. It returns a token immediately so the new account
lands straight in the workspace.

- New accounts are **always** `lecturer`. There is no way to self-register as an
  admin, and an explicit `role` in the request body is ignored rather than honoured.
- Emails are normalised to lower case, so `Lecturer@Gmail.com` and
  `lecturer@gmail.com` are the same account. A repeat sign-up returns `409`.
- Passwords must be at least 8 characters.
- Set `AUTH_REGISTRATION_ENABLED=false` to close sign-ups and hide the link in the
  SPA; admins can still create users by hand.
- Optionally restrict to specific providers with
  `AUTH_REGISTRATION_ALLOWED_DOMAINS=["gmail.com"]` (an empty list, the default,
  accepts any valid address).

### Sign in with Google

Standard OAuth 2.0 authorization-code flow, abstracted behind a provider interface
so no Google code reaches business logic.

1. Create a **Web application** OAuth client in the Google Cloud console.
2. Add your callback as an authorized redirect URI, e.g.
   `http://localhost:8000/api/v1/auth/google/callback`, and set the authorized
   JavaScript origin to the same origin that serves the UI.
3. Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` and
   `GOOGLE_OAUTH_REDIRECT_URI` in `backend/.env`.

`GET /api/v1/auth/methods` is how the SPA discovers whether to offer Google; it
reports `google_enabled: false` unless the client id, secret **and** an absolute
redirect URI are all present, and the button is hidden rather than shown broken.
`GOOGLE_OAUTH_REDIRECT_URI` must be absolute — Google rejects relative paths — and
must match the registered value exactly.

How the token stays out of the URL:

1. `GET /auth/google/start` mints an unguessable `state`, stores it in Redis with a
   TTL, and redirects to Google.
2. `GET /auth/google/callback` validates `state` (rejecting replay and CSRF),
   exchanges the code server-side, verifies the ID token audience, then looks up or
   provisions the lecturer account.
3. Instead of a token, the callback issues a **one-time** Redis code
   (`GOOGLE_OAUTH_EXCHANGE_TTL_SECONDS`, default 300 s) and redirects to
   `GOOGLE_OAUTH_FRONTEND_REDIRECT` (default `/login?code=…`).
4. The SPA immediately exchanges that code via `POST /auth/google/exchange`. The code
   is consumed on first use via `GETDEL`, so a replayed callback or a leaked URL
   yields nothing.

Google is only used for identity. First-time users are provisioned with a random
unusable password, so they can never sign in with a password until an admin sets
one.

## Frontend

The SPA lives in `backend/frontend/` (React + TypeScript, Vite). It uses `BrowserRouter` (`/dashboard`, `/documents`, etc.) and is served by FastAPI's `SpaStaticFiles` mount at `/`.

Build the bundles before serving in production:

```bash
cd backend/frontend
npm ci
npm run build
```

The frontend calls the API at the same origin.

### Screens

- **Login** — email + password, plus "Sign in with Google" when configured; handles
  the one-time code returned by the Google callback
- **Register** — lecturer self-service sign-up, shown only while registration is enabled
- **Dashboard** — aggregate stats, recent documents, Moodle connection card
- **Upload** — drag-and-drop PDF upload with XHR progress bar, optional title/description/shortname/category
- **Documents** — table of all uploaded documents with live processing status
- **Document detail** — processing stepper (validate → extract → normalize → structure → chunk → analyze), dependency resolution, curriculum generation trigger
- **Curriculum** — weekly plan view, workload, learning objectives, review workflow, content QA run with verdict/findings/coverage, assessment generation & review, link to generate & review that week's lessons
- **Lesson review** — per-week lesson list with status badges; block-by-block approve/reject/regenerate/delete; source map; whole-lesson approve/reject (`/curriculum/:id/content/:unitId`)
- **Publish** — Moodle course name/shortname/category overrides, idempotent publish + verify
- **Published courses** — list with Moodle IDs, verify button
- **System status** — detailed Moodle check (category visibility, site info)

## Migrations

Alembic is the production schema authority. Run migrations inside the API container:

```bash
docker compose exec api alembic upgrade head
```

To create a new migration after model changes:

```bash
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
```

Migrations live in `backend/alembic/versions/`.

## Testing

```bash
# From the backend directory, with the project venv active
cd backend
python -m pytest -q

# Lint (from repo root or backend)
python -m ruff check .
```

The suite is 380 unit/route tests (services, repositories, moodle client, state machine, job queue, curriculum planner, course content, lesson review, route handlers, topic canonicalization, content QA, and assessment generation). Tests run without Docker or a live database (Redis queues and Postgres are faked).

## Architecture

```
backend/
├── app/
│   ├── api/v1/          # FastAPI routers
│   ├── core/            # Config, exceptions, logging, security, redis
│   ├── db/              # Repository layer (SQLAlchemy 2.x async)
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic v2 request/response schemas
│   ├── services/        # Business logic
│   │   ├── ai/          # LLMProvider interface + OpenRouter/OpenAI providers
│   │   ├── ingestion/   # Extraction, structure, chunking, job queue, state machine
│   │   ├── content_analysis/  # LLM topic/concept/pre-requisite extraction
│   │   ├── topics/       # Canonicalization, dedup, topic importance
│   │   ├── dependency/  # Prerequisite graph: cycles, topological sort
│   │   ├── planner/     # Weekly curriculum planning
│   │   ├── curriculum/  # Curriculum + review workflow
│   │   ├── qa/          # Content QA rules, QA service, coverage reports
│   │   ├── assessment/  # Unit/final assessment generation + review
│   │   ├── moodle/      # Moodle REST client, mapper, publishing/sync, lesson renderer
│   │   ├── course_content/  # LLM lesson generation, rendering, review workflow
│   │   └── overview.py  # Document overview aggregation
│   └── workers/         # Background worker process (asyncio + Redis polling)
├── alembic/             # Database migrations (versions/ committed)
├── frontend/            # React + TypeScript SPA (Vite)
├── scripts/             # CLI helpers (run from the backend directory)
├── docker-compose.yml
└── .env                 # Local configuration (git-ignored)

scripts/
├── run_demo.py          # End-to-end CLI demo (--publish requires Moodle creds)
├── demo_course_content.py  # Generate/review/publish a week's lessons (see docs/course-content.md)
└── generate_sample_textbook.py
```

Key design principles:

- **API → Service → Repository → Database** (no business logic in route handlers)
- **LLM providers abstracted** behind `LLMProvider` (OpenRouter production default, OpenAI opt-in) — AI-dependent code never touches a provider SDK directly
- **No LLM calls inside database transactions**; blocking extraction runs off the event loop
- **Idempotent Moodle publish** via course `idnumber` find-or-create; publish/verify paths never delete Moodle data
- **No fabricated data** — all displayed counts and statuses are real persisted state
- **Permissive external checks** — Moodle or LLM failures never crash the API