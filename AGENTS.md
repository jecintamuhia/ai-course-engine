# AI Course Engine — Project Instructions

## Project Purpose

AI Course Engine ingests educational textbooks/documents, extracts and structures their content, and generates a configurable course curriculum that can later be published to Moodle.

Current priority:

* Document ingestion
* Text extraction
* Structure detection
* Chapters
* Sections
* Topics
* Concepts/subtopics
* Learning objectives
* Prerequisites/dependencies
* Difficulty/workload estimation
* 4-month / 16-week curriculum planning
* Lecturer review before publishing

Do NOT implement future features unless explicitly requested.

## Technology Stack

* Python 3.12+
* FastAPI
* Pydantic v2
* SQLAlchemy 2.x
* PostgreSQL
* Alembic
* pytest
* Docker / Docker Compose
* Moodle integration through an adapter
* Optional Redis/background workers where appropriate

## Architecture

Maintain clear separation between:

* API/routes
* Application/services
* Domain models
* Repositories
* Infrastructure
* Database models
* External integrations

Prefer:

API → Service → Repository → Database

Do not put business logic directly inside FastAPI route handlers.

## AI/LLM Rules

LLM providers must be abstracted behind provider interfaces.

Do not hard-code a specific AI provider into business logic.

LLM calls must NOT occur inside database transactions.

Store provenance for AI-generated or extracted content where appropriate.

Never fabricate textbook content.

If extraction is uncertain, preserve uncertainty rather than inventing information.

## Database Rules

* Use SQLAlchemy 2.x patterns.
* Use Alembic for schema changes.
* Never modify the database schema manually when a migration is required.
* Do not delete existing data or tables without explicit approval.
* Avoid unnecessary schema changes.
* Preserve existing migrations.

## API Rules

* Use Pydantic v2 schemas.
* Keep request and response schemas separate from persistence models where appropriate.
* Maintain backward compatibility unless a breaking change is explicitly requested.
* Return clear HTTP errors.
* Validate external input.

## Coding Rules

Before changing code:

1. Inspect the relevant existing implementation.
2. Understand the current architecture.
3. Identify dependencies and side effects.
4. Make the smallest appropriate change.
5. Run relevant tests.
6. Fix failures caused by the change.
7. Summarize what changed.

Do not rewrite large portions of the project unnecessarily.

Do not introduce new dependencies unless they are justified.

Prefer simple, maintainable Python over clever abstractions.

## Git Rules

Never run destructive Git commands without explicit approval.

Do not use:

* git reset --hard
* git clean -fd
* force push
* destructive branch operations

Do not overwrite unrelated user changes.

## Testing

When modifying functionality:

* Add or update tests where appropriate.
* Run the relevant pytest tests.
* Prefer focused tests first.
* Run the broader test suite when practical.

Do not claim tests pass unless they were actually executed.

## Documentation

Update documentation when behavior or architecture changes.

Keep documentation factual.

Never claim functionality exists if it has not been implemented.

## Working Style

When a task is ambiguous:

* Inspect the repository first.
* Explain the ambiguity.
* Make reasonable assumptions only when low-risk.
* Ask before making architectural changes.

For larger tasks:

1. Analyze
2. Propose approach
3. Implement
4. Test
5. Review

Always protect existing functionality.
