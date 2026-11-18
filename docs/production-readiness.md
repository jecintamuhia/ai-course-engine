# Production Readiness and Approval Gates

Status date: 2026-11-18.

Repository-side validation is complete for the current Docker Compose target.
**Production launch is not approved.** No OCI resource has been provisioned,
no DNS record has been changed, no production certificate has been requested,
no Google OAuth credential has been configured, and no production data has been
migrated.

Use this page with [`oci-deployment.md`](oci-deployment.md) and
[`oci-operations.md`](oci-operations.md). Hosting choices are compared in
[`hosting-options.md`](hosting-options.md). A separate non-production Render
staging proposal is in
[`render-staging-deployment.md`](render-staging-deployment.md); it does not
replace any production approval gate.

## 1. Current verified state

| Check | Result | Evidence |
| --- | --- | --- |
| Backend test suite | 731 passed in 59.92s | `python -m pytest -q`, 2026-11-18 |
| Frontend component tests | 23 passed (5 files) | `npm run test -- --run`, 2026-11-18 |
| Frontend typecheck | Passed (`tsc --noEmit`) | 2026-11-18 |
| Frontend production build | Passed (`tsc --noEmit` + `vite build`) | 2026-11-18 |
| Scoped Python lint | `python -m ruff check app tests scripts` passed | 2026-11-18 |
| Root Python lint | `python -m ruff check .` passed | 2026-11-18 |
| Byte-compile | `python -m compileall -q app` passed | 2026-11-18 |
| Alembic heads | Exactly one head: `f1a2b3c4d5e6 (head)` | `python -m alembic heads`, 2026-11-18 |
| CI workflow files | `tests.yml` has backend/frontend gates; `deploy.yml` is manual-only and deploys nothing | `tests.yml` run #11 passed both jobs (id `44271152336`, commit `3e5ec8abd8c2ec7ce84cd82e12680b332a98f04c`, 2026-11-18T08:56:23Z); required merge check pending |
| Backend test suite (historical) | 697 passed | `python -m pytest -q`, 2026-11-17 |
| Backend test suite (historical) | 660 passed | `python -m pytest -q`, 2026-11-04 |
| Production config validation | Unsafe production values rejected; safe test values accepted | `backend/app/core/config.py`, `backend/tests/test_config.py` |
| Environment preflight | Valid staging env passed; example env failed on intentional placeholders | `deploy/oci/validate_env.py`, 2026-11-04 |
| Compose configuration | Resolves when `.env.production` exists (example copied) | `docker compose ... config` |
| Caddy configuration | `Valid configuration` | `caddy validate` |
| Shell scripts | `bash -n` passed | `deploy/oci/*.sh` |
| Local full-stack smoke test | PostgreSQL, Redis, migration, API readiness, auth methods, both workers, and local Caddy HTTPS passed | Disposable local run |
| Backup/restore round trip | PostgreSQL dump/restore, storage archive/restore, migration, and API readiness passed | Disposable local run, 2026-11-04 |
| ARM64 image build | Previously validated for `linux/arm64/v8` | OCI image build evidence |

The backup/restore round trip used the same `pg_dump -Fc`, `pg_restore
--clean`, tar, migration, and readiness sequence as the scripts. The
`backup.sh` / `restore.sh` wrappers themselves require a Linux host with Docker
and root for the restore path; they were syntax-checked here but not executed
through their root guard on Windows.

## 1.1 Readiness classification

| Dimension | Status | Basis |
| --- | --- | --- |
| Code and repository gates | **GREEN locally** | 731 backend tests, 23 frontend tests, typecheck, build, Ruff, compile, single Alembic head |
| CI execution gate | **ESTABLISHED (enforcement pending)** | `tests.yml` run #11 passed both jobs after dependency/environment fixes; make it a required merge check |
| Staging/integration readiness | **NOT ESTABLISHED** | No non-production Moodle exists; no live publish, read-back, learner progression or certificate verification |
| Operational readiness | **NOT ESTABLISHED** | No approved host, DNS, TLS, secrets, first admin, target backup/restore or production environment verification |
| Security verification | **INCOMPLETE** | Code/config review only; `npm audit` advisories remain; no external penetration or load test |
| Client acceptance | **NOT ESTABLISHED** | 21 OPEN decisions in `docs/client-decision-register.md`; one owner direction recorded but no written approval; SRD/architecture/API/ERD empty |

These dimensions must not be collapsed into a single "ready" claim. Passing
local code gates does not establish staging, operational, security or client
acceptance readiness.

## 2. Blocking owner approvals

Nothing below may be inferred, fabricated, or bypassed.

| Gate | Required owner action | Blocked until |
| --- | --- | --- |
| Hosting provider and cost | Approve OCI Always Free or an alternative Docker host and a maximum monthly cost | Provider decided |
| OCI capacity, if chosen | Confirm tenancy, MFA, A1 capacity, and permission to create the VM/network | VM can be created |
| DNS | Approve the exact `api.skillupactionafrica.co.ke` record in HostAfrica/cPanel; do not change apex or `www` without separate approval | API hostname resolves |
| TLS | Supply an authorized ACME contact email for Caddy | Certificate can be requested |
| Google OAuth | Supply client id/secret and approve the callback, or explicitly keep sign-in disabled | OAuth can be enabled |
| Client decision register | Approve every applicable entry in `docs/client-decision-register.md`, including identity, enrolment, assessment and certification policy | Owner approval recorded |
| Manual assessment marking | Confirm objective-only scope in writing (owner direction recorded 2026-11-18), or approve the exact grading workflow | Manual marking formally excluded or implemented |
| Non-production Moodle | Supply staging URL/token, bundled plugin, required functions/capabilities, test category and rollback plan | Staging checklist can be executed |
| Moodle production | Supply the production URL/token and confirm the required web-service permissions; preserve all Moodle data and publishing records | Live Moodle verification or publishing |
| CI enforcement | Make the passing `tests.yml` check required on `main`; keep `deploy.yml` manual-only | Required merge check configured |
| Dependency security | Approve remediation for `npm audit` advisories and an upgrade policy for breaking fixes | Security findings triaged |
| AI provider | Supply the production key/model and an approved spend limit | Ingestion/content generation can run |
| Source data | Identify an authoritative production database/storage export, or approve starting empty | Migration can begin |
| Secrets and admin | Provide production secrets and the first administrator email through an approved secure channel | Deployment can start |
| Launch | Review the verification evidence and sign off | Public launch |

The prepared Google callback is:

```text
https://api.skillupactionafrica.co.ke/api/v1/auth/google/callback
```

The Google callback is configuration only. It has not been registered with
Google or verified by Google.

## 3. Security and authorization checks

- Production settings reject the default/placeholder `SECRET_KEY`, short
  secrets, `DEBUG=true`, non-PostgreSQL database URLs, non-HTTPS frontend/CORS
  origins, localhost production URLs, placeholder AI/Moodle credentials, and
  incomplete Google credential pairs.
- `JWT_ALGORITHM` is restricted to `HS256`, `HS384`, or `HS512`.
- CORS origins and allowed hosts are explicit; wildcard origins are rejected.
- Self-registration creates only `student` accounts. Admin-only user creation is
  the sole path to `lecturer`, `teacher`, or `admin`.
- `app/services/auth/routing.py` is the source of truth for post-login routing.
- Staff endpoints are gated by `require_staff`; learner endpoints by
  `require_learner` and are scoped to the caller's own records.
- Google OAuth remains disabled when credentials are empty. The current
  `/auth/google/start` behavior is covered by tests and returns `401` while
  disabled; enabling it requires the approval gate above.
- PostgreSQL and Redis are private to the Compose network. Caddy is the only
  service with published host ports and adds security headers.
- Upload size is capped at 50 MB by default.
- No secret, private key, token, `.env`, or production environment file is
  included in this repository change.
- Login, registration, and Google sign-in start are protected by Redis-backed
  throttling in `backend/app/services/auth/rate_limit.py`; there is no permanent
  account lockout. The throttling policy is implemented but not client-approved.
- `npm audit --omit=dev --audit-level=high` reported 14 advisories (3 moderate,
  11 high), including a high `picomatch` chain and moderate
  `postcss-selector-parser`/`react-router` advisories. No dependency upgrade was
  applied because the known `tailwindcss` remediation is breaking. `pip-audit`
  was unavailable, so no Python dependency audit was run.

This is a configuration and code review, not an external penetration test or a
load test.

## 4. Moodle preservation rules

- Do not overwrite, migrate, or delete Moodle data or publishing records.
- Do not use `skillupafrica.co.ke` as a substitute for
  `skillupactionafrica.co.ke`; they are different systems.
- Do not enable live publishing until the token, permissions, category, and
  rollback behavior are approved and verified.
- A read-only Moodle check may be performed only after credentials are supplied.
- Existing Railway and OCI configuration is not authorization to publish.

## 5. Launch sequence after approval

Run from `deploy/oci` on the approved Linux host:

```bash
python3 validate_env.py
docker compose --env-file .env.production -f compose.yaml config >/dev/null
bash bootstrap.sh
docker compose --env-file .env.production -f compose.yaml up -d --build
docker compose --env-file .env.production -f compose.yaml ps -a
```

Then:

1. Confirm the `migrate` service exited `0`.
2. Confirm `/health/ready` and `/api/v1/health`.
3. Confirm the API hostname and TLS certificate.
4. Create the first administrator with `scripts/create_admin.py`; never put the
   password on the command line.
5. Log in as admin and verify dashboard access.
6. Create or verify lecturer/teacher accounts, then test learner registration
   and routing.
7. If a source export was approved, restore it with `restore.sh`, then verify
   row counts, constraints, Alembic head, and document-file counts before
   allowing users in.
8. Run a read-only Moodle connection check. Do not publish until separately
   approved.

## 6. Rollback and recovery

- Keep the source database/storage untouched until the target is verified.
- Take a fresh backup before any restore over an existing target.
- `restore.sh` is destructive to the target database; it requires root on the
  VM and takes a safety backup unless `SKIP_BACKUP=1` is explicitly set.
- Store backup archives off the VM, not only under `deploy/oci/data/backups`.
- Keep the Railway fallback files, but do not describe them as a deployed
  production service.
- DNS rollback requires the same owner approval as DNS cutover.
- Do not use destructive Git commands as part of deployment or rollback.

## 7. Known limitations

- Final assessment auto-grading covers `multiple_choice`, `true_false`, and
  `short_answer` with a stored correct answer. Scenario, practical, coding, and
  matching items are shown but excluded from scoring. "Open-ended" is not an
  item kind; generic manual assessment marking is not implemented. Owner
  direction recorded 2026-11-18 is that objective-only assessment is acceptable;
  written client approval is still pending. The exact policy questions are in
  `docs/client-decision-register.md`.
- OCR is not implemented. PDFs with no extractable text now fail with an
  explicit OCR-required error instead of producing a misleading empty result.
  Analysis responses include non-fatal warnings for truncated context,
  insufficient content, and empty chapters.
- Identity, enrolment, assessment, certification, hosting, staging, and launch
  decisions remain open. `docs/client-decision-register.md` records 21 OPEN
  decisions; no written client approval has been found. Draft decision records
  exist for authentication direction, course ownership and JWT lifecycle.
- GitHub Actions execution is verified: `tests.yml` run #11 passed both jobs
  after fixing missing Ruff, invalid `ENVIRONMENT=test`, and missing
  `fakeredis`/`reportlab` dependencies. Required merge-check enforcement is
  pending.
- Staging Moodle integration is blocked by external dependency; the draft
  checklist has not been executed. The production Moodle URL/token is never
  verification evidence and was not used.
- No browser automation, accessibility, responsive-device, load, or penetration
  test was performed. `npm audit` advisories remain open; `pip-audit` was not
  available.
- `docs/SRD.md`, `docs/architecture.md`, `docs/API.md`, and `docs/ERD.md` are
  empty, so agreed acceptance criteria are missing.
- OCI tenancy, A1 capacity, and cost are unconfirmed.
- `api.skillupactionafrica.co.ke` does not currently resolve.
- No production ACME certificate or OAuth verification has occurred.
- No authoritative production data source has been identified.
- The full stack has been validated locally, not on OCI.
- The backup/restore round trip was validated with disposable local data, not
  on the approved target.
- Moodle live access and publishing remain unverified.
- Login, registration, and Google sign-in start have Redis-backed throttling
  but no permanent account lockout; edge controls and the exact policy still
  need owner approval before public exposure.
- External security testing and load testing have not been performed.

## 8. Sign-off

| Role | Name | Decision | Date |
| --- | --- | --- | --- |
| Application owner |  |  |  |
| Infrastructure owner |  |  |  |
| Moodle administrator |  |  |  |

Launch is approved only when every applicable row in section 2 is resolved,
every applicable entry in `docs/client-decision-register.md` has written owner
approval, and the checks in section 1 have been repeated on the approved target.
Local code readiness alone is not sufficient; staging/integration, operational,
security and client-acceptance readiness must each be established separately.
