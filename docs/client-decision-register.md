# Client Decision Register

Date: 2026-11-18
Status: **DRAFT — NO WRITTEN CLIENT APPROVAL RECORDED**

Owner direction recorded in this workspace on 2026-11-18: objective-only
assessment is acceptable. This is not written client approval and does not close
the assessment decision.

This register lists unresolved product and architectural decisions that block
production/client acceptance. It does not record decisions on the client's
behalf. Recommendations are engineering options only and must not be treated as
approved policy.

No approved SRD exists in this repository: `docs/SRD.md`, `docs/architecture.md`,
`docs/API.md`, and `docs/ERD.md` are empty. Requirements have been reconstructed
from `AGENTS.md`, `README.md`, the compliance audit, and the platform docs. All
entries below therefore require written client approval unless explicitly
marked as owner verification only.

## Protected areas

Until the corresponding decision is approved, do not silently change:

- Identity architecture
- Course ownership
- Enrolment rules
- Authentication policies
- Assessment rules
- Certification rules

## Decision register

| ID | Decision | Current state | Implication if decided incorrectly | Recommended option (not approved) | Written client approval |
| --- | --- | --- | --- | --- | --- |
| DR-AUTH-DIRECTION | Application-owned identity vs Moodle-native sign-in | Application owns registration, JWT, roles, learner records; Moodle delivers content. Original direction was Moodle-native. Draft record exists. | Identity, enrolment, progress and certificates diverge from Moodle; late rework needs protocol, mapping, deprovisioning and role decisions. | Accept the application-owned portal, document the Moodle boundary, and reconcile `docs/moodle-public-access.md`. | **Required** |
| DR-JWT-LIFECYCLE | Access-token TTL, refresh, revocation and logout | HS256 bearer tokens, 720-minute default TTL, no `jti`, refresh token, denylist or server-side logout. Draft record exists. | Stolen tokens remain valid until expiry; shortening TTL alone causes abrupt sign-outs without revocation. | Short-lived access tokens plus rotating refresh, server-side revoke/logout, and SPA expiry/401 handling. | **Required** |
| AUTH-POLICY | Rate limiting, lockout, proxy trust, Google sign-in policy and token storage | Redis login throttling exists; no permanent lockout; `trust_proxy_headers` defaults false and uses right-most XFF only when enabled; first Google sign-in follows registration policy; token stored in SPA local storage. | Security posture may not match client expectation; public deployment assumptions may be wrong. | Keep implemented controls, accept "throttling without permanent lockout", and obtain explicit acceptance of proxy and token-storage posture. Also correct the stale `production-readiness.md` statement that says no rate limiting exists. | **Required** |
| ENROLMENT-RULES | Who may join/leave a course and which system is authoritative | Application-side self-enrolment into `SYNCED` courses; idempotent; withdrawal preserves records; enrolment gates content and assessment. | Client may expect Moodle cohorts, enrolment keys, approval or capacity limits; two conflicting sources of truth. | If DR-AUTH-DIRECTION is application-owned, declare app-side enrolment authoritative and Moodle enrolment read-only; decide open vs approved/cohort/capacity rules. | **Required** |
| DR-COURSE-OWNERSHIP | Single-tenant trust vs per-course lecturer ownership | `Course` has no owner field; all staff can read/mark all courses. Draft record exists. | Acceptable only under explicit single-tenant acceptance; otherwise a security/product defect and potentially breaking data backfill. | Use per-course ownership if lecturers handle distinct courses or data is sensitive; use single-tenant only with written pilot acceptance. Resolve assigner, override, granularity and backfill. | **Required** |
| ASSESSMENT-RULES | Scoring scope, pass mark, attempts and manual marking | Objective auto-grading only; open-ended types displayed but excluded; no manual assessment marking; 70% pass; append-only attempts; best passing attempt wins. Owner direction recorded 2026-11-18: objective-only acceptable; written approval not supplied. | A client expecting scenario/coding/practical marking receives a non-compliant product; `matching` classification may be contested. | Confirm objective-only scope in writing, including 70%, attempt policy and item classification; otherwise approve a defined manual-marking workflow. | **Required** |
| CERTIFICATION-RULES | Eligibility, reference format, presentation and download | 100% approved-lesson completion plus one passing attempt; idempotent public verification; `SKU-{YEAR}-{12 hex}`; no PDF/download. | Client may expect branded PDF, signatory or different eligibility/reference rules. | Keep snapshot fields and reference format unless changed; approve template, signatory and PDF/download requirement. | **Required** |
| OCR-SCOPE | Born-digital only vs scanned-textbook ingestion | No OCR. Text-free PDFs fail with an explicit OCR-required error; DOCX already guarded. | Real textbooks may be unprocessable, or unnecessary OCR scope/cost may be added. | Obtain the source-textbook decision; if scanned, approve OCR scope/dependency; otherwise accept OCR out of scope with the explicit failure. | **Required** |
| AI-PROVIDER-AND-SPEND | Provider, model, key and cost ceiling | Provider abstraction exists; OpenRouter default; no production key; real quality unmeasured. | Output quality, grounding and cost remain unmeasured; wrong model/key changes both. | Supply key/model and approved spend limit, then run one measured real-textbook extraction/generation/QA acceptance run. | **Required** |
| SOURCE-DATA | Authoritative production data export vs empty start | No approved export identified; only synthetic sample content used. | Migration/data-loss risk and no acceptance evidence on real client content. | Identify and approve an export or approve starting empty; align with OCR decision. | **Required** |
| SRD-ACCEPTANCE | Approved SRD, architecture, API and ERD as acceptance baseline | All four documents are empty; requirements reconstructed. | Compliance cannot be judged and conflicts cannot be resolved against an approved baseline. | Write and approve the four documents with agreed scope and acceptance criteria. | **Required** |
| STAGING-MOODLE-ACCESS | Non-production Moodle instance, plugin, token, capabilities and writes | No staging instance configured; only production Moodle credentials exist in `backend/.env`; production must not be used. | Live publishing/learner delivery remains unverified; misdirected writes risk real data. | Provide a disposable non-production Moodle with the bundled plugin, required functions, `mod/page:view`, a test category and rollback plan. | **Required** |
| STAGING-CHECKLIST-EXECUTION | Approve and execute the staging checklist | `docs/staging-integration-checklist.md` is draft and not executed. | 16-week publish/read-back, every lesson body, real learner progress and certificate verification remain unevidenced. | Execute all checks against the approved non-production site only, recording IDs, timestamps and request IDs without tokens. | **Required** |
| PRODUCTION-MOODLE-APPROVAL | Production publishing approval and rollback | Publishing prohibited until token, permissions, category and rollback are approved; no production write has been performed. | Unauthorized writes or data loss; publishing to the wrong system. | Require a separate post-staging approval plus an explicit rollback plan; keep publishing manual. | **Required** |
| CI-OWNERSHIP | GitHub Actions verification and merge enforcement | `tests.yml` covers backend/frontend gates; `deploy.yml` is a manual-only gate. Successful `tests.yml` run #11 (id `44271152336`, commit `3e5ec8abd8c2ec7ce84cd82e12680b332a98f04c`, 2026-11-18T08:56:23Z) verified after fixing missing Ruff, invalid `ENVIRONMENT=test`, and missing `fakeredis`/`reportlab` test dependencies. | Merge enforcement is not yet configured; regressions can still reach the target. | Make `tests.yml` a required check; keep deployment manual-only unless changed explicitly. See live Actions for subsequent head status. | **Required** if changing deployment semantics; otherwise owner verification |
| BROWSER-A11Y-LOAD-PEN | Commission browser, accessibility, responsive, load and penetration testing | Not performed; no Playwright/Cypress/axe/Lighthouse/chromedriver runtime installed. | Unknown UX, accessibility, load and security defects may cause client rejection. | Commission and record the required test passes with named scopes, tools, environments and sign-off. | **Required** |
| HOSTING-AND-COST | Hosting provider, cost ceiling and infrastructure capacity | OCI Always Free or alternative not approved; tenancy/MFA/A1 capacity unconfirmed. | No approved deployment target; unexpected cost; VM/network cannot be created. | Approve provider, maximum monthly cost, tenancy/MFA/A1 capacity and creation authority. | **Required** |
| DNS-TLS-GOOGLE-OAUTH | API hostname, ACME contact and Google OAuth credentials | `api.skillupactionafrica.co.ke` does not resolve; no ACME email; Google disabled and callback unregistered. | No public HTTPS or OAuth; unauthorized DNS changes. | Approve the exact API record, supply ACME email, and either supply Google credentials/callback approval or keep sign-in disabled. | **Required** |
| SECRETS-AND-FIRST-ADMIN | Production secrets and first administrator email | No production secrets or first admin email supplied. | No administrator can create staff accounts; credential leakage risk. | Provide secrets and first admin email through an approved secure channel and bootstrap via `scripts/create_admin.py`. | **Required** |
| BACKUP-RECOVERY-AND-PROD-ENV | Verify environment, backup and recovery on the approved target | Backup/restore validated only with disposable local data; target environment and root-guard path not exercised. | No verified recovery path on production. | Repeat config validation and a controlled backup/restore on the approved target before launch. | **Required** |
| LAUNCH-SIGNOFF | Final application/infrastructure/Moodle acceptance | Sign-off table blank; launch explicitly not approved. | Acceptance claimed without gates closed. | Complete sign-off only after every applicable gate above is resolved and final checks are repeated. | **Required** |

## Manual assessment marking: exact decisions needed

The repository has no approved client grading policy. The assessment schema
supports `multiple_choice`, `true_false`, `short_answer`, `scenario`,
`practical`, `coding`, and `matching`. Current scoring uses only the first three;
the other four are displayed but excluded from scoring. The service explicitly
states there is no lecturer marking step for final assessments, and the attempt
model has no manual-mark, feedback, grader or marking-status fields. Practical
hand-ins, not assessment attempts, are the only manually marked artifacts today.

Owner direction recorded in this workspace on 2026-11-18 is that objective-only
assessment is acceptable. Written client approval is still required. If that
direction is confirmed in writing, the questions below are deferred; if it is
not, the client must answer them before implementation.

Before implementing manual assessment marking, the client must answer:

1. Which item types require manual marking: all of `scenario`, `practical`,
   `coding`, and `matching`, or a subset? What does "open-ended" mean, given it
   is not an item kind?
2. Should `matching` be auto-graded from its structured options instead of
   manually marked?
3. Who may mark assessment attempts, and must course ownership be enforced?
4. How does a lecturer find pending attempts, and where does marking happen?
5. Is marking per item or one attempt-level mark? Are points, percentages,
   integer marks or decimal marks used?
6. How is the stored rubric scored, and is a written rationale mandatory?
7. How do manual marks enter the final score: weights, denominator, rounding,
   and whether the existing 70% threshold still applies?
8. Can an attempt be pending instead of immediately passed/failed, and are
   further attempts allowed while marking is pending?
9. When are correct answers, explanations, rubric details and lecturer comments
   released to the learner?
10. Can marks be edited, by whom, until when, with what reason or superseding
    record?
11. Can manually marked items be revised or resubmitted?
12. Must certification wait for manual marks, and which attempt score is
    snapshotted when several attempts exist?
13. What immutable audit history is required: previous marks, feedback, reasons,
    approver, timestamp and finalization?

No academic policy has been invented in this register.
