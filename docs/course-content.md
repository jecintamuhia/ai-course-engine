# Course Content Pipeline

Per-topic lesson generation, lecturer review, source grounding, and Moodle
lesson publishing on top of an approved curriculum.

## Terminology

- **Lesson** — one teaching unit for a weekly curriculum unit (a week).
  State: `DRAFT`, `GENERATING`, `FAILED`, `AWAITING_REVIEW`, `APPROVED`,
  `REJECTED`.
- **Lesson content block** — an ordered building block within a lesson.
  Review state: `PENDING`, `APPROVED`, `REJECTED`.
- **Source map** — per-block provenance: the textbook pages and text spans
  a block was generated from (never fabricated; blocks with no grounding
  carry an explicit source-note marker).

## Block types

| Type | Purpose |
|---|---|
| `text` | Prose explanation grounded in the source text |
| `diagram` | ASCII/Mermaid diagram with caption |
| `knowledge_check` | Question + correct answer + distractors, with page citation |
| `activity` | Practical exercise with estimated minutes and answer |
| `resource` | Link/reading with label and URL |
| `video` | Supplementary video placeholder (title, duration, attribution) |

## Generation

`CourseContentService.generate_week(curriculum_unit_id)`:

1. Loads the weekly unit and its topics from the approved curriculum.
2. Keeps any existing `APPROVED`/`AWAITING_REVIEW` lessons untouched —
   only re-generates `DRAFT`/`FAILED` lessons.
3. For each topic, sends the topic's extracted source chunks to the LLM
   (provider abstracted behind `LLMProvider`; OpenRouter production
   default). Output is validated against a Pydantic schema with a bounded
   schema-correction retry; generation never runs inside a DB transaction.
4. New lessons start as `AWAITING_REVIEW` so the lecturer sees them in the
   review UI without an extra submit step.

LLM calls are batched per topic's chunks, not over the full textbook, and
blocks are limited in number so requests stay small. Provenance is stored
per lesson (`source_chunks`) and per block (`source_refs`, page citations).

## Review workflow

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/course-content/weeks/{unit_id}/generate` | Generate/regenerate lessons for a week |
| `GET` | `/api/v1/course-content/weeks/{unit_id}/lessons` | List lessons for a week (with statuses) |
| `GET` | `/api/v1/course-content/lessons/{lesson_id}` | Lesson detail with blocks |
| `GET` | `/api/v1/course-content/lessons/{lesson_id}/source-map` | Block → source provenance |
| `POST` | `/api/v1/course-content/lessons/{lesson_id}/submit-for-review` | Move a DRAFT/FAILED lesson to `AWAITING_REVIEW` |
| `POST` | `/api/v1/course-content/lessons/{lesson_id}/review` | Approve/reject a lesson (lecturer name + comments) |
| `POST` | `/api/v1/course-content/blocks/{block_id}/review` | Approve/reject one block with optional comments |
| `POST` | `/api/v1/course-content/blocks/{block_id}/regenerate` | Re-generate a single rejected block |
| `POST` | `/api/v1/course-content/blocks/{block_id}` (DELETE) | Delete a block |

A lesson is only publishable when its status is `APPROVED`. Reviewing a
block marks the lesson back to `AWAITING_REVIEW`/`REJECTED` as appropriate
so the lecturer re-approves changed content before it can be published.

## Moodle lesson publishing

Only `APPROVED` lessons are published. On `POST /api/v1/moodle/publish/{id}`
the route:

1. Loads approved lessons via `LessonRepository.list_publishable_by_curriculum`
   (eager-loads blocks).
2. Builds the renderer with `build_lesson_renderer(lessons)` from
   `app/services/moodle/lessons.py` — groups approved lessons by unit,
   ordered by week then position.
3. Passes it to `MoodleSyncService.publish_curriculum(..., lesson_renderer=...)`.

`build_course_plan` calls the renderer once per unit and attaches the
resulting lessons to the weekly section plan. Lessons render to HTML via
`render_lesson_html(lesson, include_answers=True)` — the lecturer-friendly
page (definitions, diagrams, knowledge checks, activities, resources,
attribution) with answers included.

Lesson pages are added as Moodle `Page` activities **idempotently** (by
matching page name within the section) and are never modified once created.
Re-publish after approving more lessons to attach them. Each week is a
single Moodle section with its lesson pages; no separate page is generated
for the week itself. Within a unit, lessons with byte-identical rendered
content are collapsed to one page, so duplicated lesson items never create
duplicate Moodle pages (distinct lessons that share a title are kept).
Lesson pages are included in post-publish verification; a missing lesson
page fails verification, records `SYNC_FAILED`, and leaves the curriculum
`APPROVED`.

## Frontend

`pages/LessonReview.tsx` at route `/curriculum/:curriculumId/content/:unitId`
supports: generate lessons for the week, list lessons with status badges,
expand and review a lesson block-by-block (approve/reject/regenerate/
delete), view the source map, then approve/reject the lesson with reviewer
name and comments. It is reached via the "Generate & review lessons for
this week" link on the curriculum studio page.

## CLI demo

`backend/scripts/demo_course_content.py` drives the services directly
(from the `backend` directory, with the venv active; on the host point
`DATABASE_URL` at `localhost:5432` because `backend/.env` uses the
docker-internal `postgres` hostname):

```bash
$env:DATABASE_URL="postgresql+asyncpg://course_engine:course_engine@localhost:5432/course_engine"
.venv\Scripts\python scripts\demo_course_content.py [--curriculum <uuid>] [--week 1]
```

It picks the latest APPROVED/PUBLISHED curriculum (or `--curriculum`),
generates the given week's lessons, approves one generated lesson, and
publishes to Moodle when `MOODLE_URL`/`MOODLE_TOKEN` are configured. It
never deletes or fabricates data.