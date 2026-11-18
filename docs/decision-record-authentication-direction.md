# Decision Record: Authentication Direction

**Status:** OPEN — REQUIRES CLIENT APPROVAL
**Decision owner:** Client
**Sources:** `AGENTS.md`, `docs/client-requirements-compliance-audit.md`
(findings 6.5 and 6.10), `docs/moodle-integration.md`,
`docs/production-readiness.md`, working tree.

This record recommends an option; it does not record a client decision. No
approval is claimed and no authentication or Moodle integration code was
changed for this record.

## Context

The audit records the original direction as Moodle-native learner sign-in. The
working tree instead implements application-owned identity and a learner portal,
while Moodle remains the delivery surface for course content. The split affects
accounts, enrolment, progress, assessment records and certificates; it needs
written client acceptance or an architecture change.

## Current implementation

- Roles are `admin`, `lecturer`, `student` and `teacher`. Self-registration
  (`POST /api/v1/auth/register`) always creates `student`;
  `POST /api/v1/auth/users` is admin-only and is the sole path to staff or
  `teacher` accounts.
- Password login, optional Google sign-in and application JWT issuance are
  implemented. `app/services/auth/routing.py` is the source of truth for
  `role -> redirect_to`; the SPA honours the server value.
- `require_staff` gates the authoring workspace; `require_learner` gates the
  learner portal and its endpoints return only the caller's own records.
- This application's database is authoritative for enrolment, milestones,
  practical submissions, assessment attempts, marks, feedback and certificates.
  Moodle is read for course structure and lesson bodies and written to on
  publish only.
- Enrolment is application-side (`/api/v1/learner/courses/{id}/enrol`) and
  gates access to published content. No Moodle-native learner login, LTI/SSO
  bridge, Moodle account provisioning or enrolment synchronisation exists.
- The current working tree applies registration enablement and domain policy to
  first Google sign-in
  (`backend/app/services/auth/service.py:164`); the audit's 6.10 wording is
  historical. Google remains disabled without configured credentials.
- No staging or production Moodle learner journey has been exercised here.

## Options

| Option | Summary | Consequence |
| --- | --- | --- |
| A. Accept application-owned portal | Keep local registration/login, role routing and the application database as the learner record of truth; Moodle delivers content. | Matches current code; requires documented identity/enrolment boundary and written acceptance. |
| B. Moodle-native learners | Move learner sign-in and enrolment to Moodle; link application records to Moodle identities. | Requires protocol choice, identity mapping, enrolment sync, deprovisioning and role mapping; significant architecture change. |
| C. Hybrid | Application-owned staff; Moodle-native learners bridged into the portal. | Preserves authoring workflow but still needs identity linking, session handling and enrolment sync. |

## Recommendation (not a decision)

Choose **A** for the current scope: it preserves the implemented role boundary,
self-registration and authoritative learner records, with Moodle used for
content delivery only. If the client requires **B** or **C**, treat it as a new
architecture decision with a migration and integration plan; do not approximate
it with client-side redirects or a shared token.

## Client decision needed

1. Is application-owned learner registration/login acceptable, or is
   Moodle-native sign-in mandatory?
2. If Moodle-native sign-in is required: which protocol/IdP, how are Moodle and
   application user ids linked, and how are staff accounts handled?
3. Which system owns enrolment, progress, assessment results and certificates,
   and how are withdrawals/deprovisioning synchronised?
4. Is the current Google sign-in exception/registration policy acceptable?

## Status

OPEN — REQUIRES CLIENT APPROVAL. Finding 6.5 remains open in the audit; this
document does not close it.
