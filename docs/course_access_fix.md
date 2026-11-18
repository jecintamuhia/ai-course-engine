# SkillUp Action Africa — Learner / Lecturer Course Access Fix

## 1. Root-cause analysis

### Symptom
When a learner (or lecturer) opened a published course or lesson from the
SkillUp Action Africa portal, the user was sent away from the application to
Moodle to read the actual lesson content.

### Tracing the user journey
1. A lecturer approves a curriculum and publishes it.
   - `MoodleSyncService.publish_curriculum` (backend/app/services/moodle/sync.py)
     creates/updates the Moodle course and adds one Moodle **Page** activity
     per lecturer-approved lesson (via the bundled `local_ai_course_engine`
     plugin: `local_ai_course_engine_add_page`).
   - The Moodle course id and URL are stored on the internal `Course` record
     (`moodle_course_id`, `moodle_url = {MOODLE_URL}/course/view.php?id=...`).
2. The learner enrols via `/api/v1/learner/courses/{course_id}/enrol`.
3. The learner opens the learner portal (`/learn`) and selects a course.
4. `Learn.tsx` and `LearnerCourse.tsx` displayed an **"Open on Moodle"**
   button whose `href` was `course.moodle_url`, i.e.
   `{MOODLE_URL}/course/view.php?id=<moodle_course_id>`.
5. Clicking it navigated the browser out of the SkillUp portal to the Moodle
   course view — the Moodle delivery surface, not a SkillUp-native lesson
   viewer.
6. The lesson content itself (the rendered Page HTML) lived only in Moodle.
   The portal had no endpoint that retrieved the published course structure
   (sections, section order, page modules) or the individual lesson page
   content from Moodle.

### Root cause
Course-content delivery was **fully delegated to Moodle via an external link**;
the SkillUp portal never retrieved the published Moodle curriculum itself.
There was:

* no backend endpoint to resolve an internal course/lesson to its Moodle
  records and read the published sections/modules/page content;
* no native lesson-content viewer route in the frontend;
* the only "open course/lesson" action was the `moodle_url` external link.

That external link is the redirect the task refers to. Note: the link targeted
the Moodle **course view** (`course/view.php?id=...`), which is the content
delivery surface — not the Moodle site-administration dashboard. The
administration dashboard was never used as the course-access destination.
Nevertheless, the architectural defect is the same: course access left the
SkillUp portal for Moodle instead of rendering the published curriculum
in-portal.

### What was NOT the cause
* Not an incorrect Moodle URL — `moodle_url` is correctly built from
  `MOODLE_URL` + `course/view.php?id=...` (`sync.py:_course_url`).
* Not an admin-dashboard URL being reused — no admin URL was used.
* Not missing course-content retrieval endpoints because none existed — they
  had to be added.
* Not Moodle authentication/session handling — the portal uses its own JWT;
  Moodle is contacted server-side with `MOODLE_TOKEN` (never exposed to the
  browser).
* Not incorrect role assignments — `require_learner` / `require_staff` already
  gate the surfaces; enrolment already gates learner course content.

## 2. Existing vs corrected course-access flow

### Existing flow (faultful)
```
Learner selects course on /learn
  -> "Open on Moodle" link: GET {MOODLE_URL}/course/view.php?id=N
  -> Browser leaves SkillUp portal; lesson content read on Moodle
  -> Progress/milestones tracked locally on return (if learner comes back)
Lecturer reviews learners at /reviews (no course-content viewer)
```

### Corrected flow (native in-portal delivery)
```
Learner selects course on /learn/course/:courseId
  -> GET /api/v1/learner/courses/:courseId/content
     (require_learner + active-enrolment check)
     -> MoodleCourseContentService resolves Course -> moodle_course_id
        -> core_course_get_contents(moodle_course_id)
     -> returns published sections (weeks) + page modules (lessons)
  -> Learner clicks a lesson -> /learn/course/:courseId/lesson/:lessonId
     -> GET /api/v1/learner/courses/:courseId/lessons/:lessonId/content
        -> resolve Lesson (must belong to course curriculum, APPROVED)
        -> find Moodle Page module named == lesson.title
        -> return its HTML body (contents[0].content)
     -> rendered in-portal; completion is a separate explicit action
  -> Lesson completion -> POST .../complete (existing milestone logic, unchanged)
Lecturer views course content
  -> GET /api/v1/lecturer/courses/:courseId/content  (require_staff)
  -> GET /api/v1/lecturer/courses/:courseId/lessons/:lessonId/content  (require_staff)
  -> learner progress remains at /reviews (existing)
```

Key invariant: Moodle remains the source of published curriculum content; the
portal retrieves it server-side through the existing authenticated Moodle
integration (`core_course_get_contents`, already required for publishing
verification) and renders it in-portal. No Moodle administrator credentials,
service token, or secret config reaches the browser.

## 3. Implemented changes

### Backend
* **`app/services/moodle/content.py`** (new) — `MoodleCourseContentService`:
  * `get_course_structure(course_id)` — resolves the internal `Course` record,
    requires `moodle_course_id` (raises a clear `MoodleIntegrationError` when
    the course was never published), calls `core_course_get_contents`, and
    normalises sections/modules into `MoodleCourseStructure`.
  * `get_lesson_content(course_id, lesson_id)` — verifies the lesson belongs
    to the course's curriculum, finds the matching Moodle Page module by
    lesson title, and returns its HTML body. Raises a clear 404
    (`LessonNotFound`) when the lesson was never published to Moodle — never
    fabricates content.
  * Read-only Moodle calls only; `MOODLE_TOKEN` stays server-side.
* **`app/schemas/moodle.py`** — new Pydantic schemas:
  `MoodleModuleRead`, `MoodleSectionRead`, `MoodleCourseStructureRead`
  (includes `moodle_url`), `MoodleLessonContentRead`.
* **`app/core/dependencies.py`** — new `get_moodle_content_service`
  dependency (shared by learner and lecturer routers).
* **`app/services/learner/service.py`** — new `require_enrolment(user,
  course_id)` helper (403 when not enrolled, 404 when course missing).
* **`app/api/v1/learner.py`** — two new endpoints:
  `GET /learner/courses/{course_id}/content` and
  `GET /learner/courses/{course_id}/lessons/{lesson_id}/content`,
  both `require_learner` + enrolment check.
* **`app/api/v1/lecturer.py`** — two new endpoints:
  `GET /lecturer/courses/{course_id}/content` and
  `GET /lecturer/courses/{course_id}/lessons/{lesson_id}/content`,
  both `require_staff`.

### Frontend
* **`src/lib/types.ts`** — `MoodleModuleRead`, `MoodleSectionRead`,
  `MoodleCourseStructureRead`, `MoodleLessonContentRead`.
* **`src/lib/api.ts`** — `learnerCourseContent`, `learnerLessonContent`,
  `lecturerCourseContent`, `lecturerLessonContent`.
* **`src/pages/LearnerCourse.tsx`** — rewritten as the native curriculum
  viewer: loads the Moodle course structure and renders weeks/sections with
  lesson cards linking to the in-portal lesson page. "View on Moodle" is now a
  secondary link to the Moodle course view (not the admin dashboard).
* **`src/pages/LearnerLesson.tsx`** (new) — in-portal lesson viewer:
  renders the Moodle Page HTML (`dangerouslySetInnerHTML`), shows practical
  task hand-ins, and offers the explicit complete/uncomplete action. Content
  is readable before completion.
* **`src/pages/LecturerCourse.tsx`** (new) — read-only lecturer course
  curriculum + lesson viewer under `/lecturer/courses/:courseId` and
  `/lecturer/courses/:courseId/lessons/:lessonId`.
* **`src/App.tsx`** — added routes
  `/learn/course/:courseId/lesson/:lessonId`,
  `/lecturer/courses/:courseId`, `/lecturer/courses/:courseId/lessons/:lessonId`
  (lecturer routes sit in the staff-guarded `AppShell` group).

### Moodle Web Services / permissions
* No new Moodle web service function is required for **reading** content:
  `core_course_get_contents` (already in the preflight requirements, gated by
  `moodle/course:view`) returns sections and, for Page modules,
  `contents[0].content` (the page HTML). Publishing already uses
  `local_ai_course_engine_add_page` / `local_ai_course_engine_update_section`
  via the bundled plugin.
* Reading therefore needs only the already-required capability
  `moodle/course:view` on the token. No administrator privileges are granted
  to lecturers; lecturer access is bounded by the existing `require_staff`
  role boundary.
* If the connected Moodle does not return page `contents` (older build or
  restricted token), content is reported as unavailable with a clear error
  rather than fabricated — see the "not published" 404 path.

## 4. Preserved behavior
* Publishing, verification, enrolment, withdrawal, practical-task
  submission/grading, milestones, lecturer progress review (`/reviews`),
  authentication, and role separation are unchanged and still exercised by
  the existing test suite.
* Lesson completion remains an explicit action; opening a lesson does **not**
  mark it complete. Completion rules and idempotency (first record wins) are
  untouched.
* Moodle failures surface as clear `MoodleIntegrationError` (502) responses;
  missing courses/lessons return 404; unenrolled access returns 403. No
  fabricated curriculum or false completion states.

## 5. Moodle activity types still needing additional integration
The reader currently surfaces Moodle **Page** activities (the published lesson
bodies) via `core_course_get_contents`. The following activity types are
published to Moodle only as part of lesson content HTML or not at all through
the read path, and would need dedicated handling for full interactivity:
* **Quiz** (`mod_quiz`) — weekly-unit and course-final assessments are
  generated locally and reviewed; they are not exposed as retrievable Moodle
  quiz attempts through this change.
* **Assignment / workshop** (`mod_assign`, `mod_workshop`) — practical tasks
  are handled as local hand-ins (`/learner/courses/{id}/blocks/{id}/submit`);
  Moodle assignment submissions are not read back.
* **Forum**, **URL**, **File**, **Label**, **H5P**, **SCORM**, **LTI** — may
  appear as modules but are not individually rendered; only Page module HTML
  is retrieved.
* Embedded media / interactive activities that require Moodle-hosted
  rendering (e.g. video players, interactive H5P) — images/diagrams embedded
  in Page HTML render in-portal; anything requiring a Moodle session or
  Moodle-specific JS would need a secure iframe/embedding integration or a
  documented "View on Moodle" fallback rather than an admin redirect.

## 6. Test results
Run from `backend/` with the project venv:

```
python -m pytest -q
```

* Before the change: **618 passed**.
* After the change: **634 passed** (16 new tests), 0 failed.
* `ruff check .`: clean.
* Frontend `npm run typecheck` (`tsc --noEmit`): clean.

New tests:
* `tests/unit/test_moodle_content.py` — service unit tests (structure
  retrieval, section/module mapping, lesson content by title, not-published
  404, wrong-curriculum 404, not-published 404, Moodle failure surfaces as a
  clear error).
* `tests/unit/test_learner_content_api.py` — route tests (learner course
  content returns Moodle structure, learner lesson content returns page HTML,
  enrolment required -> 403 `not_enrolled`, unknown course -> 404, lesson not
  published -> 404 `lesson_not_found`, endpoints require auth -> 401, no
  `wstoken` leakage, lecturer `require_staff` admits lecturers).

No learner or lecturer course-access action redirects to the Moodle
administration dashboard; the only Moodle link is the optional secondary
"View on Moodle" to the course view.
