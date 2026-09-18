# AI Course Engine

Production-oriented platform for AI-assisted educational content ingestion, knowledge extraction, curriculum planning, lecturer review, and Moodle publishing.

## Current status

A working MVP covering the end-to-end flow:

1. **Upload** a PDF textbook
2. **Ingestion** — extract text, detect chapter/section structure, chunk into semantic segments (background worker)
3. **AI analysis** — extract topics, concepts, and prerequisites via LLM
4. **Dependency resolution** — topological ordering of topics, cycle detection, prerequisite mapping
5. **Curriculum generation** — deterministic weekly planner (16 weeks by default, configurable) that always spans exactly the requested number of weeks, spreads topics across the full horizon within workload budgets, and carries per-week learning objectives
6. **Lecturer review** — submit-for-review / approve / reject workflow
7. **Moodle publish** — idempotent course creation with sections + weekly page resources; verify after publish
8. **Web UI** — same-origin SPA served by FastAPI; sidebar navigation across all screens

**Current limitation:** AI analysis (step 3) requires a running LLM. The provider architecture supports OpenRouter (production default) and OpenAI. Production uses OpenRouter's API with structured outputs; each chapter's extraction completes quickly using a bounded per-chapter context (~6000 chars) and a compact schema to keep requests small. The prompt spells out the nested shape (each concept is an object with `name`/`description`), and schema violations are retried with the corrected schema; header-only/TOC pages whose text is shorter than `AI_MIN_CONTENT_CHARS` are skipped without an LLM call. Transient failures (rate limits, provider overload, timeouts) are retried with bounded exponential backoff; permanent errors (invalid key, insufficient credits) fail fast.

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
| `POST` | `/curricula/{id}/submit-for-review` | Move to lecturer review queue |
| `POST` | `/curricula/{id}/review` | Record approve/reject decision |
| `GET` | `/courses` | Published Moodle courses |
| `GET` | `/moodle/status` | Moodle connection status (permissive) |
| `GET` | `/moodle/check` | Deep Moodle health check (read-only) |
| `POST` | `/moodle/publish/{curriculum_id}` | Publish approved curriculum to Moodle |
| `POST` | `/moodle/verify/{course_id}` | Verify course exists in Moodle |

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

- **Dashboard** — aggregate stats, recent documents, Moodle connection card
- **Upload** — drag-and-drop PDF upload with XHR progress bar, optional title/description/shortname/category
- **Documents** — table of all uploaded documents with live processing status
- **Document detail** — processing stepper (validate → extract → normalize → structure → chunk → analyze), dependency resolution, curriculum generation trigger
- **Curriculum** — weekly plan view, workload, learning objectives, review workflow
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

The suite is 196 unit/route tests (services, repositories, moodle client, state machine, job queue, curriculum planner, route handlers). Tests run without Docker or a live database (Redis queues and Postgres are faked).

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
│   │   ├── dependency/  # Prerequisite graph: cycles, topological sort
│   │   ├── planner/     # Weekly curriculum planning
│   │   ├── curriculum/  # Curriculum + review workflow
│   │   ├── moodle/      # Moodle REST client, mapper, publishing/sync
│   │   └── overview.py  # Document overview aggregation
│   └── workers/         # Background worker process (asyncio + Redis polling)
├── alembic/             # Database migrations (versions/ committed)
├── frontend/            # React + TypeScript SPA (Vite)
├── docker-compose.yml
└── .env                 # Local configuration (git-ignored)

scripts/
├── run_demo.py          # End-to-end CLI demo (--publish requires Moodle creds)
└── generate_sample_textbook.py
```

Key design principles:

- **API → Service → Repository → Database** (no business logic in route handlers)
- **LLM providers abstracted** behind `LLMProvider` (OpenRouter production default, OpenAI opt-in) — AI-dependent code never touches a provider SDK directly
- **No LLM calls inside database transactions**; blocking extraction runs off the event loop
- **Idempotent Moodle publish** via course `idnumber` find-or-create; publish/verify paths never delete Moodle data
- **No fabricated data** — all displayed counts and statuses are real persisted state
- **Permissive external checks** — Moodle or LLM failures never crash the API