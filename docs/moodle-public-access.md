# Moodle Public Access — Student & Teacher Experience

This document covers the client requirement: *anyone from outside the
organisation can come to the Skillup Action Africa Moodle site, create an
account or sign in, find published courses, and learn from them.*

**Architecture principle:** Moodle owns course content delivery, enrolment and
the course catalogue. This application is the authoring tool (admin/lecturer
only) that publishes approved curricula into Moodle, **and** the learner
portal where a learner's own progress, assessments and certificates live.
The two surfaces share one sign-in: a `student` or `teacher` account that
authenticates here lands on the learner portal (`/learn`), which links out to
the Moodle course. See §12 for the role model and post-login routing.

---

## 1. Intended experience

```
Visitor
→ https://elearning.skillupafrica.co.ke  (Skillup Action Africa branding)
→ Create account / Sign in            (Moodle-native auth)
→ Moodle dashboard
→ Find published course               (Moodle catalogue/search)
→ Enrol                             (Moodle enrolment)
→ Open course → Week n → Lesson/Page activity
```

The same site is used by **teachers** — but a public signup never creates
a teacher (see §5).

---

## 2. Verified live state (2026-10-08, read-only)

| Item | Actual state |
|---|---|
| URL | `https://elearning.skillupafrica.co.ke` |
| Moodle version | **4.3.12** (Build 20250414) |
| Site name | `Skillup Action Africa` (already set — appears on login/home) |
| Theme | `classic` (Boost-based core theme) |
| Self-registration | **Disabled** — `/login/signup.php` returns 404 “Sorry, you may not use this page” |
| Login page | Standard Moodle login: Username, Password, “Lost password?”, guest link. Signup link absent (registration disabled) |
| Password reset | Present (`/login/forgot_password.php`) |
| Course catalogue | Public — an anonymous visitor can browse `/course/index.php` and see course id 5 |
| Course id 5 | `WHM/cPanel/DirectAdmin/Plesk - Complete Professional Textbook`, `idnumber ai-ece-643a805c-…`, visible, 17 sections (General + Week 1–16); **only Week 1 has page resources** (needs re-publish to be complete) |
| Guest access | Course requires login; no anonymous guest view of course content |
| WS token function set | Publishing functions all present; preflight reports `ready: true` |
| Moodle admin web access | Not available to this workflow yet — the settings below require site admin |

---

## 3. Public registration (Moodle-native)

Currently **off**. Enabling it is a Moodle site-admin action, not a code
change. Recommended Moodle-native configuration:

1. Site administration → Plugins → Authentication → Manage authentication
   - Enable **Email-based self-registration** (`auth/email`).
   - Set **Default authentication method for users** appropriately
     (typically `Email-based self-registration`).
2. Site administration → Plugins → Authentication → Email-based
   self-registration
   - **Enable self-registration** = Yes.
   - Decide **Email confirmation** (recommended **Yes** to prevent
     address abuse).
3. Keep Moodle’s security controls intact:
   - **Password policy** (Site administration → Security → Site security
     settings / account settings): leave the site defaults enabled.
   - **CAPTCHA**: enable under Site administration → Plugins →
     Authentication → Manage authentication → common settings if spam is
     observed.
   - **Duplicate email handling**: default (reject duplicates) stays as
     is.
   - A registered user must confirm their email (if confirmation is on)
     before the account is usable — documented, not bypassed.

**Do not** build a FastAPI signup form. The signup flow is Moodle’s
`/login/signup.php`, branded via the site name and logo below.

---

## 4. Roles — student

Newly registered users get Moodle’s standard **authenticated user** role
plus (by default) **student** in any course they are enrolled into. This
is exactly the intended default: a normal authenticated/student-level
user.

Verify after enabling registration that:

- `auth_email` assigns only the default authenticated user role
  (Site administration → Users → Permissions → *Authenticated user*);
- no public user has `manager`/`teacher`/`admin`/`editingteacher` roles.

---

## 5. Teacher workflow

A public signup **must not** create a teacher. The safe, Moodle-native
workflow is:

1. A teacher registers like any student (self-registration, §3).
2. A **site admin** assigns the teacher role to the right course(s):
   - Site administration → Users → Enrolled users → pick the course → add
     the user → assign `Teacher` (or `Non-editing teacher`) locally.
   - Or, for a course the teacher should manage, set the course enrol
     instance accordingly.
3. Moodle permissions then limit the teacher to their assigned course(s).
   A teacher cannot access site administration or create courses
   site-wide by default.

**Documented rule:** never grant `Manager`/`Administrator` to a public
user. No arbitrary public registration may obtain course-management
privileges site-wide.

If the client later wants a *teacher request* workflow, it must be a
Moodle-native mechanism (e.g. a request block/course + an admin acting on
the request) — not a FastAPI endpoint.

---

## 6. Course discovery & enrolment

Discovery already works without login (`/course/index.php` is public).
After login the Moodle dashboard and the “All courses” catalogue expose
the published course.

Enrolment method is a per-course Moodle setting. For free public access,
enable **Self enrolment (`enrol_self`)** on each published course:

1. In the course → Participants → Enrolment methods → add **Self
   enrolment (Student)**
2. Role for self enrolment: **Student**
3. Enrollment key: leave blank for free open enrolment (or issue a key if
   restricted access is wanted later)
4. Require email confirmation / allow guests to enter course: per client
   preference

No payment system is introduced — the client requirements do not specify
paid courses.

Do **not** build a duplicate course catalogue in FastAPI; Moodle is the
source of truth for student-facing discovery.

---

## 7. Published vs draft

Only curricula that pass the AI Course Engine publishing gates reach
Moodle:

- Review approval (lecturer/admin) **and** fresh content-QA `pass` are
  enforced before any Moodle write (`POST /api/v1/moodle/publish/{id}`
  → `assert_qa_pass` → preflight gate → publish → verify; on failure the
  course row is recorded `sync_failed` and the endpoint reports the real
  failure). See `moodle-integration.md`.
- Re-publishing uses the stored `idnumber` (find-or-create), upserts
  sections by number, and adds pages only when missing — it never
  duplicates courses/sections/pages.
- Course 5 currently holds **partial** content (Week 1 only) from an
  earlier publish attempt; it is the *same* idnumber as the real
  curriculum and is updated in place by the next successful publish, so
  no deletion is required or should be performed.

---

## 7.1 Learner progress and hand-ins (application, not Moodle)

Moodle is the **content delivery surface only**. Everything a learner does
after they start studying is recorded in the application database, and the
learner never needs a Moodle account to make progress:

| Learner action | Recorded in | Moodle role |
|---|---|---|
| Joining a course | `learner_enrolments` | None — enrolment is app-side only |
| Finishing a lesson | `learner_milestones` | None — Moodle does not report completion |
| Handing in a `practical_task` | `practical_submissions` | None — hand-ins are text/markdown in the app |
| Marking and feedback | `practical_submissions.grade` / `.feedback` | None — grades live in the app |
| Lecturer activity trail | `lecturer_activities` | None |

Practical implications:

- Do not enable Moodle completion tracking or gradebook for these courses;
  it would create a second, conflicting source of truth.
- Moodle enrolment in the published course grants *reading access to the
  material* only. It is not a substitute for the app's `learner_enrolments`
  row, which is what gates the learner portal.
- A learner can therefore hold a Moodle course access without being enrolled
  in the app (and the reverse); neither state is derived from the other.
- The app's learner portal (`/learn`) is the surface where progress and
  hand-ins are shown; the lecturer review surface (`/reviews`) is where
  submissions are marked.

---

## 8. Branding — Skillup Action Africa

Use Moodle-native theme settings only (no Moodle core edits, no fragile
fork). Recommended:

1. **Site name** — already `Skillup Action Africa`. ✓ (login/home header)
2. **Logo** — the official artwork is now in the repository; upload it via
   Site administration → Appearance → Logos (header + login).
   - Full lockup: `backend/frontend/public/brand/skillup-action-africa-logo.png`
   - Compact lockup (also used by the login panel): `backend/frontend/public/brand/skillup-action-africa-logo-sm.png`
   - Symbol only: `backend/frontend/public/brand/skillup-action-africa-mark.png`
   - Favicon: `backend/frontend/public/favicon.png`
   - All four are derived mechanically from the logo published on
     `skillupafrica.co.ke` by `scripts/prepare_brand_assets.py`; the artwork
     is never redrawn or recoloured.
3. **Favicon** — Appearance → Theme → `classic` → favicon upload
   (`backend/frontend/public/favicon.png`).
4. **Theme** — `classic` is active; keep core and override via theme
   settings/CSS *only if* needed, and document any custom CSS. Prefer
   standard theme settings.
5. **Login/signup** — with the site name already set, the login page shows
   “Log in to **Skillup Action Africa**”; the signup page will show the
   same branding once self-registration is enabled and a logo is
   uploaded.
6. **Login brand panel** — `moodle-theme/skillup-auth/` contains a
   paste-ready branded panel for the login page (no Moodle core files
   touched, no theme fork):
   - Paste `moodle-theme/skillup-auth/skillup-auth-head.html` into
     Site administration → Appearance → Additional HTML (**HEAD**).
   - Paste `moodle-theme/skillup-auth/skillup-auth-hero.html` into the
     same page (**BODY**).
   - The panel shows the official logo (inlined as a data URI, exactly as
     the organisation's own site does) and uses the official palette.
7. **Course experience** — the course page header uses the site name; the
   custom logo completes it.

---

## 9. Required Moodle admin checklist

Actions that require the Moodle site administrator (blocked until admin
access is available):

1. Enable **Email-based self-registration** (§3) — with email
   confirmation on.
2. Enable **Self enrolment** on the published course (§6) with Student as
   the default enrol role.
3. Upload the **Skillup Action Africa logo** + favicon (§8) and paste the
   login brand panel (§8.6).
4. Verify the default **authenticated user** role (§4) and that no public
   user is a teacher/admin.
5. Re-publish the WHM curriculum from the AI Course Engine so course 5
   contains all 16 weeks (its quality gate must also pass — see
   `whm-phase2-progress.md`).

---

## 12. Role model & post-login routing

The application recognises four roles. Two author, two learn.

| Role | May use the workspace? | Post-login destination |
| --- | --- | --- |
| `admin` | Yes | Authoring workspace `/dashboard` |
| `lecturer` | Yes (authoring; user management stays admin-only) | Authoring workspace `/dashboard` |
| `student` | No — `403` on every workspace endpoint | Learner portal `/learn` |
| `teacher` | No — `403` on every workspace endpoint | Learner portal `/learn` |

- **Single source of truth:** `app/services/auth/routing.py` defines the
  staff and learner roles and computes the destination. The login,
  register, and Google-exchange responses all carry a `redirect_to` field
  that the SPA honours; no course id is ever embedded.
- **Server-side enforcement:** every authoring/publish/Moodle route
  requires the `require_staff` dependency (`admin` or `lecturer`);
  `student`/`teacher` tokens get `403 authorization_error`. The SPA route
  guard is a convenience on top of this, not the security boundary.
- **Learner portal:** `student`/`teacher` accounts land on `/learn`, a
  learner surface served by this application (`app/api/v1/learner.py`).
  Every endpoint on it returns only the calling account's own records.
  Moodle remains the delivery surface for the course content itself —
  the portal links out to it.
- **No escalation:** public self-registration (`POST /auth/register`)
  always creates a `student` and cannot request a role; only an admin may
  create users of an arbitrary role (`POST /auth/users`). A Google
  sign-in on a new address creates a `student` too.
- **Configurable destination:** `LEARNER_DESTINATION` (default `/learn`)
  may be a same-origin path or an absolute URL. If it is blank the
  sign-in path is returned, so the response always yields a destination.


---

## 10. Security notes (public flow)

- No Moodle web-service token, OAuth secret, API key, or DB credential is
  exposed by the AI Course Engine API (`/api/v1/moodle/status`,
  `/preflight`, `/courses` never echo the token; covered by tests).
- FastAPI authentication exists for the authoring workspace and the learner
  portal. To keep public registration on Moodle only, set
  `AUTH_REGISTRATION_ENABLED=false` in `backend/.env` (it defaults to
  `true` and creates learner accounts for the portal; the frontend already
  hides its signup link when disabled). Learner accounts in this
  application are then created by an admin only. `student`/`teacher`
  accounts are rejected by every workspace endpoint with `403` and land on
  the learner portal on sign-in (see §12).
- Moodle’s own controls (email confirmation, password policy, CAPTCHA,
  duplicate-email rejection) must be left at their secure defaults — §3
  explicitly does not weaken them.
- No public signup path grants site administration, user management, or
  web-service administration.

---

## 11. Acceptance test script (to run once the admin actions are applied)

Public user (fresh account):

1. `https://elearning.skillupafrica.co.ke` → Skillup Action Africa
   branding visible.
2. “Create new account” → complete Moodle signup → confirm email (if
   enabled) → sign in → Moodle dashboard.
3. Course catalogue/dashboard → find `WHM/cPanel/DirectAdmin/Plesk -
   Complete Professional Textbook`.
4. Self-enrol → open course → Week 1 → a lesson page opens.
5. Open a later week (e.g. Week 13) → a lesson page opens.

Teacher:

6. Register as a normal user; confirm role is not a teacher.
7. Admin assigns “Teacher” role on the course; teacher then edits only
   that course.

Each step above must be exercised live before being reported as done.