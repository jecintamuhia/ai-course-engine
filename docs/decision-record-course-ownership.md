# Decision Record: Course Ownership

**Status:** OPEN — REQUIRES CLIENT APPROVAL
**Decision owner:** Client
**Sources:** `AGENTS.md`, `docs/client-requirements-compliance-audit.md`
(finding 6.8 / D9), `docs/production-readiness.md`, working tree.

This record recommends an option; it does not record a client decision. No
approval is claimed and no schema or code change was made for this record.

## Context

Four roles exist. `admin` and `lecturer` use the authoring workspace and
lecturers review lessons, publish to Moodle and mark learner hand-ins. The
audit records that any lecturer can currently read and mark any course and
treats this as acceptable only under an explicitly accepted single-tenant
model. Course ownership therefore changes both the authorization model and the
deployment trust assumption.

## Current implementation

- `Course` (`backend/app/models/course.py:22`) has no owner, creator or
  assignment field; it tracks curriculum, Moodle publication metadata and sync
  state only.
- Lecturer endpoints (`backend/app/api/v1/lecturer.py:52`) require
  `require_staff`; no per-course ownership predicate exists in the lecturer
  service or repositories.
- `admin` is the only role allowed to create users
  (`POST /api/v1/auth/users`); self-registration always creates `student`.
- No ownership migration has been added. No live/staging Moodle check or
  multi-lecturer acceptance test has been performed.

## Options

| Option | Summary | Consequence |
| --- | --- | --- |
| A. Single-tenant trust model | All staff are trusted with all courses; document the assumption and acceptance. | No schema change. Requires written client acceptance; unsuitable if lecturers must be separated. |
| B. Course ownership | Add an owner/assignment relation, enforce it in repositories/services and filter lecturer routes and UI. | Needs an Alembic migration, backfill rule, admin assignment path, tests and UI changes. Admin override must be defined. |
| C. Publish separation only | Restrict Moodle publishing to admins while leaving review/marking global. | Partial risk reduction; does not resolve cross-lecturer reading or marking. |

## Recommendation (not a decision)

Choose **B** if more than one lecturer may work on distinct courses or if
course data is sensitive between lecturers. Choose **A** only for a deliberately
single-tenant pilot with written acceptance. Do not add an ownership column or
silent filtering before the client chooses; an incorrect assignment model would
be a breaking product and data-migration decision.

## Client decision needed

1. Is the deployment single-tenant with all staff trusted, or is per-course
   ownership required?
2. If ownership is required: is it per course, curriculum or Moodle course;
   who assigns it; may admins override; and how are existing courses backfilled?
3. Must lecturers be prevented from seeing other courses' learners, submissions
   and activity, or only from marking them?

## Status

OPEN — REQUIRES CLIENT APPROVAL. The audit finding remains as recorded; this
document does not close it.
