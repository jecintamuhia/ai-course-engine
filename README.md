# AI Course Engine

Production-oriented backend foundation for AI-assisted educational content ingestion, knowledge extraction, curriculum planning, and Moodle integration.

## Current milestone: Phase 1 — Foundation

Phase 1 establishes the runtime and infrastructure boundaries only. Domain models, AI extraction, curriculum planning, and Moodle synchronization remain intentionally out of scope until the foundation is verified.

Implemented:

- FastAPI application with versioned API routing
- `/health` liveness endpoint
- `/readiness` dependency readiness endpoint
- typed Pydantic v2 configuration
- structured JSON logging
- request correlation IDs
- application exception hierarchy and safe error responses
- async SQLAlchemy 2.x database/session foundation
- PostgreSQL configuration
- Redis readiness integration
- Alembic async migration configuration
- Docker Compose PostgreSQL, Redis, and API services
- pytest foundation and API tests
- Ruff and mypy project configuration

## Local development

1. Copy `.env.example` to `.env` and replace the development secret.
2. Start infrastructure:

```bash
docker compose up -d postgres redis
```

3. Create the database schema through Alembic:

```bash
cd backend
alembic upgrade head
```

4. From the repository root, start the API:

```bash
uvicorn app.main:app --app-dir backend --reload
```

5. Run tests:

```bash
pytest -q
```

## Configuration

Application configuration is environment-driven. See `.env.example` for the supported foundation settings. Secrets must never be committed to Git.

## Migrations

Alembic is the production schema authority. SQLAlchemy `create_all()` is intentionally not used as a production initialization strategy.

Phase 1 contains a foundation revision with no domain tables. Domain schema begins in Phase 2 and will be introduced through subsequent migrations.

## Verification

The repository's Phase 1 verification includes:

- Python compilation
- unit/API tests
- Alembic revision discovery
- live Uvicorn `/health` smoke test

A real PostgreSQL migration, Docker build, and Docker Compose integration test require Docker/PostgreSQL availability in the execution environment.