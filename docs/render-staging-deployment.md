# Render / Vercel / Neon / Upstash Staging Deployment Report

Status date: 2026-11-04.

**No staging resource has been provisioned, no DNS record has been changed, and
nothing in this report authorises a deployment.** This is a readiness report and
configuration plan for owner approval.

The proposed staging stack is:

```text
Vercel (React SPA)
        |
        | HTTPS + CORS
        v
Render web service (FastAPI + co-located ingestion worker)
        |                         |
        |                         +--> persistent disk /app/storage
        |
        +--> Neon PostgreSQL
        +--> Upstash Redis (TLS)
        +--> OpenRouter

Render background worker (content generation)
        +--> Neon PostgreSQL
        +--> Upstash Redis (TLS)
        +--> OpenRouter
```

Staging is deliberately isolated from production Moodle. No Moodle URL or token
is supplied, so Moodle publishing is disabled.

## 1. Readiness summary

| Area | Status | Notes |
| --- | --- | --- |
| Backend test suite | Ready | `660 passed` on 2026-11-04. |
| Python lint | Ready | `ruff check app tests` passed. |
| Frontend production build | Ready | `tsc --noEmit && vite build` passed. |
| Backend container | Ready | Dockerfile builds Python 3.12, runs as `appuser`, expects `$PORT`. |
| Health probes | Ready | `/health/ready` checks PostgreSQL and Redis; `/api/v1/health` is liveness. |
| Migrations | Ready | Alembic migrations are the schema authority. |
| Login throttling | Ready | Redis-backed, fails closed with `503` if Redis is unavailable. |
| Neon URL handling | Code-ready | `sslmode` is translated to asyncpg `ssl`; `channel_binding` is dropped. |
| Persistent uploads | Conditional | Requires a paid Render web service plus a disk. Free web services have ephemeral storage. |
| Ingestion worker | Conditional | Can run inside the API service so it shares the upload disk. |
| Content worker | Conditional | Requires a separate paid Render background worker. Free tier does not include workers. |
| Staging access control | Not ready | No application-level staging gate exists. The site is public if deployed. |
| Staging Moodle | Blocked | No staging Moodle credentials exist; production Moodle must not be used. |
| Staging hostnames | Blocked | Render and Vercel hostnames cannot be finalised until services are created. |
| Cost approval | Blocked | Owner has not approved recurring spend. |

## 2. Provider configuration

No `render.yaml` is committed. The repository has no approved Render service
names, hostnames, or credentials, and committing a Blueprint before approval
would encode guessed values. Use the dashboard settings below, or add a
Blueprint only after the owner approves the exact names and environment.
Provider-generated hostnames must be recorded when they exist.

### 2.1 Render web service: API and ingestion worker

Create a **new** Render service. Do not modify an existing production service.

| Setting | Value |
| --- | --- |
| Service type | Web Service |
| Runtime | Docker |
| Name | `skillup-staging-api` (name is a proposal; the generated hostname must be recorded) |
| Repository | This repository |
| Branch | `main` |
| Root Directory | `backend` |
| Dockerfile Path | `Dockerfile` |
| Region | Choose the approved region nearest the owner and Neon; not fixed by the repository |
| Plan | `0.5c-512mb` (512 MB), required for a persistent disk |
| Instances | `1` while the disk is attached |
| Health Check Path | `/health/ready` |
| Pre-Deploy Command | `alembic upgrade head` |
| Start Command | `sh /app/scripts/start_api.sh` |
| Auto-Deploy | Off until the staging pipeline is approved |
| Persistent Disk | Name `skillup-staging-uploads`, mount `/app/storage`, size `1 GB` minimum; `5 GB` recommended |
| Disk mount effect | Uploaded documents are written to `/app/storage/documents` |
| Environment | See section 3 |

Important constraints:

- Do not scale this service above one instance while the disk is attached.
- The disk is not a backup. Define an off-host copy of `/app/storage` before
  staging holds anything that matters.
- The ingestion worker is started in-process by `start_api.sh` when
  `RUN_INGESTION_WORKER=true`. This is intentional because Render disks are
  attached to one service and the worker must read the uploaded PDFs.
- `start_api.sh` currently starts Uvicorn without `--proxy-headers`. The login
  limiter reads the right-most `X-Forwarded-For` entry directly, so throttling
  does not depend on Uvicorn proxy trust, but request logging and any future use
  of `request.client` may see the Render proxy address. Treat proxy-header
  support as a hardening item to verify, not as a completed setting.
- `/health/ready` proves both Neon and Upstash are reachable. A Redis outage
  therefore fails the Render health check as well as login throttling.

### 2.2 Render background worker: content generation

Create a second Render service from the same repository.

| Setting | Value |
| --- | --- |
| Service type | Background Worker |
| Runtime | Docker |
| Name | `skillup-staging-content-worker` |
| Root Directory | `backend` |
| Dockerfile Path | `Dockerfile` |
| Plan | `0.5c-512mb` (512 MB) |
| Instances | `1` |
| Start Command | `sh -c 'exec python -m app.workers.content_worker'` |
| Persistent Disk | None |
| Pre-Deploy Command | None |
| Environment | See section 3 |

The content worker reads curriculum data and source chunks from PostgreSQL. It
does not need `UPLOAD_DIR`, the disk, `CORS_ORIGINS`, `FRONTEND_URL`, or
`RUN_INGESTION_WORKER`.

Run migrations only from the API service. Two services running
`alembic upgrade head` at the same time is unnecessary.

### 2.3 Vercel frontend

Create a **separate** Vercel project for staging. Do not change the existing
production Vercel project or its domains.

| Setting | Value |
| --- | --- |
| Project name | `skillup-action-africa-staging` (proposal; record the actual generated hostname) |
| Root Directory | `backend/frontend` |
| Framework Preset | Vite |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node version | Use the Vercel default supported version; the repository does not pin one |
| Environment | `VITE_API_BASE_URL=https://<render-api-host>/api/v1` |
| Domain | Use the generated `*.vercel.app` hostname; do not attach a custom domain without separate approval |
| Deployment protection | Enable if the selected Vercel plan supports it and the owner approves the cost |

`backend/frontend/vercel.json` already defines the Vite build, `dist` output,
SPA rewrite to `index.html`, and long-lived cache headers for hashed assets and
the favicon.

`VITE_API_BASE_URL` is public build-time configuration, not a secret. It must
include the `/api/v1` suffix. Changing it requires a new frontend deployment.

### 2.4 Neon PostgreSQL

| Setting | Value |
| --- | --- |
| Plan | Free for initial staging, or Launch if free-plan limits are unsuitable |
| Region | Choose the approved region nearest Render; keep the API, workers, and database close |
| Database | Dedicated staging database, for example `skillup_staging` |
| Role | Dedicated staging role with access only to the staging database |
| Data | Start empty. Do not import production data without separate approval |
| Connection URL | Store the provider-issued URL as `DATABASE_URL`; never commit it |
| TLS | Required |
| Backups | Free-plan retention and restore behaviour must be reviewed before staging holds valuable data |

The application accepts `postgres://`, `postgresql://`, and
`postgresql+asyncpg://`. It converts the URL to the asyncpg scheme and translates
`sslmode` to `ssl`, dropping `channel_binding`.

If the Neon **pooled** endpoint is used, smoke-test migrations and normal queries
before declaring staging ready. PgBouncer transaction pooling can expose
asyncpg prepared-statement issues. If that happens, use one of these approved
remediation paths:

1. Use the direct Neon endpoint for the API and workers; or
2. Add an explicit asyncpg statement-cache setting in application configuration
   and cover it with tests.

Do not silently switch production to a direct endpoint without reviewing
connection limits.

### 2.5 Upstash Redis

| Setting | Value |
| --- | --- |
| Product | Upstash Redis |
| Plan | Free for initial staging; upgrade only after measuring command volume |
| Region | Choose the approved region nearest Render |
| TLS | Enabled |
| Database | Dedicated staging database |
| Connection URL | `rediss://default:<password>@<upstash-host>:6379` stored as `REDIS_URL` |
| Eviction | Do not allow key eviction that can delete queue keys without review |
| Persistence | Review before relying on the queue for long-running work |

Redis stores ingestion queues, content-generation queues, OAuth handoff state,
and login-throttling buckets. Losing Redis loses queued work and rate-limit
counters. It must not be treated as disposable while jobs are in flight.

## 3. Environment inventory

No secret values are recorded here. Set secrets through the provider dashboards
or an approved secret manager.

`ENVIRONMENT=staging` bypasses the production-only validation in
`backend/app/core/config.py`. The staging values below therefore have to be
reviewed manually; they are not enforced by the application. Do not use
`ENVIRONMENT=production` for this staging stack until production DNS, Moodle,
and approval gates are satisfied.

### 3.1 Shared by the API and content worker

| Variable | Required | Staging value or note |
| --- | --- | --- |
| `ENVIRONMENT` | Yes | `staging` |
| `DEBUG` | Yes | `false` |
| `SECRET_KEY` | Yes | Random staging-only secret, at least 32 characters. Rotating it invalidates all sessions. |
| `DATABASE_URL` | Yes | Neon staging URL, preferably the pooled URL after smoke-testing |
| `DATABASE_POOL_SIZE` | Yes | `5` per service |
| `DATABASE_MAX_OVERFLOW` | Yes | `5` per service |
| `DATABASE_POOL_TIMEOUT` | Yes | `30` |
| `DATABASE_POOL_RECYCLE` | Yes | `1800` |
| `REDIS_URL` | Yes | Upstash TLS URL beginning with `rediss://` |
| `AI_PROVIDER` | Yes | `openrouter` |
| `OPENROUTER_API_KEY` | Yes | Staging/approved key with a spend cap. The API fails startup without it. |
| `OPENROUTER_MODEL` | Yes | Owner-approved model ID |
| `LOG_LEVEL` | Yes | `INFO` |
| `LOG_JSON` | Recommended | `true` for provider log collection |
| `MOODLE_URL` | No | Leave unset for staging so publishing is disabled |
| `MOODLE_TOKEN` | No | Leave unset for staging so publishing is disabled |
| `GOOGLE_OAUTH_CLIENT_ID` | No | Leave unset; Google sign-in remains disabled |
| `GOOGLE_OAUTH_CLIENT_SECRET` | No | Leave unset; Google sign-in remains disabled |

### 3.2 API service only

| Variable | Required | Staging value or note |
| --- | --- | --- |
| `FRONTEND_URL` | Yes | Actual stable Vercel staging URL, for example `https://<vercel-staging-host>` |
| `CORS_ORIGINS` | Yes | JSON array containing the actual Vercel staging origin, for example `["https://<vercel-staging-host>"]` |
| `UPLOAD_DIR` | Yes | `/app/storage/documents` |
| `RUN_INGESTION_WORKER` | Yes | `true` |
| `AUTH_REGISTRATION_ENABLED` | Yes | `false` unless testers need public self-registration |
| `AUTH_REGISTRATION_ALLOWED_DOMAINS` | Optional | JSON array if registration is enabled, for example `["example.org"]` |
| `LEARNER_DESTINATION` | Yes | `/learn` |
| `ALLOWED_HOSTS` | Optional | JSON array for the Render hostname. This setting is present in config but is not currently enforced by middleware; do not rely on it for access control. |
| `LOGIN_RATE_LIMIT_ENABLED` | Yes | `true` |
| `LOGIN_RATE_LIMIT_EMAIL_ATTEMPTS` | Yes | `5` |
| `LOGIN_RATE_LIMIT_IP_ATTEMPTS` | Yes | `30` |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | Yes | `300` |
| `MAX_UPLOAD_SIZE_MB` | Recommended | `50` |
| `MOODLE_COURSE_CATEGORY_ID` | No | Leave unset while Moodle is disabled |

### 3.3 Content worker only

The content worker needs the shared database, Redis, AI, and logging variables.
It does not need the API-only variables above.

### 3.4 Vercel frontend

| Variable | Required | Staging value or note |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Yes | `https://<render-api-host>/api/v1` |

No secret belongs in Vercel. `VITE_*` variables are embedded in the browser
bundle and must be treated as public.

## 4. Deployment sequence after approval

The Render and Vercel hostnames depend on each other. Use this order to avoid
guessing either value.

1. Create the Neon staging database and role. Record the connection URL without
   exposing it in chat or source control.
2. Create the Upstash staging Redis database with TLS. Record the `rediss://`
   URL as a secret.
3. Create the separate Vercel staging project and import `backend/frontend`.
   Record the stable generated `*.vercel.app` hostname.
4. Create the Render API service with the disk, health check, pre-deploy
   migration, and start command from section 2.1.
5. Set the API environment, including `FRONTEND_URL` and `CORS_ORIGINS` using
   the Vercel hostname from step 3.
6. Set `VITE_API_BASE_URL` in Vercel to the Render API hostname plus `/api/v1`,
   then deploy the frontend.
7. Create the Render content worker from section 2.2 with the shared environment.
8. Confirm the API pre-deploy migration succeeded and the API is healthy.
9. Create the first staging administrator from the API shell:

   ```bash
   python scripts/create_admin.py --email <admin-email> --full-name "Staging Administrator" --role admin
   ```

   Enter the password interactively. Do not put it on the command line or in
   Render environment variables.

10. Run the verification checks in section 5.

Do not attach `skillupactionafrica.co.ke`, `api.skillupactionafrica.co.ke`, or
any production DNS record to this staging stack. Staging uses provider-generated
hostnames only.

## 5. Verification checks

### Infrastructure

```bash
curl -fsS https://<render-api-host>/health/ready
# expected: {"status":"ready"}

curl -fsS https://<render-api-host>/api/v1/health
# expected: {"status":"ok"}

curl -fsS https://<render-api-host>/api/v1/auth/methods
# expected: JSON describing enabled sign-in methods
```

### Database and storage

- `alembic current` reports the expected head revision.
- A test document upload succeeds.
- Restart or redeploy the API and confirm the uploaded file still exists.
- Confirm `/app/storage/documents` is owned by `appuser` and writable.
- Confirm a second API instance is not running while the disk is attached.

### Workers

- An ingestion job moves out of `PENDING` and reaches a terminal state.
- The content worker logs show it polling Redis and processing a queued job.
- Stopping Redis produces a readiness failure and a `503` on login, not an
  unthrottled login path.

### Application

- The Vercel SPA loads and deep links do not return a Vercel 404.
- Browser requests to the API succeed with no CORS errors.
- Admin login works and the dashboard loads.
- If registration is enabled, a new account is created as `student` and lands on
  `/learn`.
- A lecturer login lands on `/dashboard`.
- Moodle publishing remains unavailable because no Moodle credentials are set.

### Neon-specific

- Confirm migrations run successfully through the selected endpoint.
- Confirm normal read/write workloads do not raise prepared-statement errors.
- Confirm connection counts stay below the Neon plan limit with the API and both
  workers running.
- Confirm the free plan's compute suspend/resume behaviour is acceptable for
  staging. If always-on latency is required, price the Launch plan instead.

## 6. Blockers and risks

| Item | Impact | Required decision or action |
| --- | --- | --- |
| Recurring spend not approved | No paid Render service can be created | Approve a monthly maximum and the provider accounts |
| No staging accounts or credentials | Hostnames, URLs, and connectivity cannot be verified | Owner creates or authorises Neon, Upstash, Render, and Vercel access |
| No staging Moodle | Publishing and live Moodle sync cannot be tested | Supply staging Moodle credentials, or accept that Moodle stays disabled |
| No AI key or spend cap | The API refuses startup with `AI_PROVIDER=openrouter` and no key | Supply an approved staging key and a provider-side spend limit |
| Public staging site | Anyone with the URL can reach login; registration may be abused | Keep registration disabled, use deployment protection, or accept the risk |
| No off-host upload backup | Render disk loss loses uploaded documents | Approve a backup destination and schedule |
| Free Render web service | No disk, sleeps, and cannot run the paid content worker reliably | Use paid Render services for a realistic staging test |
| Proxy headers not enabled | Request logs may show the proxy address; any future `request.client` use is affected | Verify Render forwarding behaviour and enable Uvicorn proxy headers before relying on client IPs |
| Neon pooled endpoint unverified | Migrations or queries may fail with asyncpg prepared statements | Smoke-test before cutover; use the direct endpoint or add an explicit cache setting if needed |
| Vercel Hobby terms | Hobby is intended for personal, non-commercial use | Confirm eligibility or budget for Vercel Pro |
| Staging bypasses production validation | Weak secrets or non-HTTPS values will not be rejected automatically | Review every staging value manually |

## 7. Recurring cost estimate

Prices below are provider list prices observed on 2026-11-04. They exclude
taxes, exchange-rate effects, LLM usage, Moodle hosting, domain renewal, and
support plans. Reconfirm every price in the provider dashboard before purchase.

| Component | Configuration | Monthly cost |
| --- | --- | --- |
| Render API web service | `0.5c-512mb` | `$7.00` |
| Render content worker | `0.5c-512mb` | `$7.00` |
| Render persistent disk | `1 GB` at `$0.25/GB/month` | `$0.25` |
| Neon PostgreSQL | Free plan | `$0.00` |
| Upstash Redis | Free plan | `$0.00` |
| Vercel frontend | Hobby plan | `$0.00` |
| **Baseline total** | | **`$14.25/month`** |

Sensitivity:

| Change | Monthly effect |
| --- | --- |
| Render disk increased to `5 GB` | `+$1.00` (`$15.25/month` total) |
| Vercel Pro required by the Hobby non-commercial restriction | `+$20.00` (`$34.25/month` baseline total) |
| Neon Launch instead of Free | Roughly `+$15.00` for a small database (`$29.25/month` baseline total) |
| Upstash Pay-as-you-go | `$0.20 per 100K commands` plus storage/bandwidth, variable |
| Render workspace Pro | `+$25.00`; only needed if the Hobby workspace is unsuitable |

The zero-cost configuration is not recommended for this application because it
cannot provide persistent uploads or a separate content worker:

| Free-only component | Limitation |
| --- | --- |
| Render free web service | Ephemeral filesystem and spin-down; uploaded documents disappear |
| Render free tier | No background workers |
| Neon Free | Compute suspends when idle; usage limits apply |
| Upstash Free | Command, storage, and bandwidth limits apply |
| Vercel Hobby | Non-commercial-use restriction |

## 8. Rollback and cleanup

Before deleting anything, export approved staging data if it is needed.

1. Disable the Vercel staging project or remove its generated domain.
2. Suspend the Render content worker, then the Render API service.
3. Delete the Render disk only after confirming no required uploads remain.
4. Delete the Upstash staging database only after confirming no queued jobs
   remain.
5. Delete the Neon staging database only after an approved export.
6. Leave production DNS, the production Vercel project, production Moodle, and
   production data untouched.

## 9. Approval checklist

The owner must explicitly approve:

- [ ] The staging provider stack: Render, Vercel, Neon, and Upstash.
- [ ] A maximum monthly spend, including the `$20/month` Vercel Pro and
      `$15/month` Neon Launch contingencies if required.
- [ ] Creation of new staging accounts and services.
- [ ] The staging data policy: start empty, no production import.
- [ ] Whether staging may be publicly reachable.
- [ ] Whether self-registration stays disabled.
- [ ] Whether staging Moodle remains disabled.
- [ ] The AI provider key and its spend cap.
- [ ] The Render disk size and backup destination.
- [ ] The exact Render and Vercel hostnames once generated.

No deployment should start until these approvals are recorded.

## 10. References

- Render pricing: <https://render.com/pricing>
- Render disks: <https://render.com/docs/disks>
- Render free-tier limitations: <https://render.com/docs/free>
- Render Blueprint specification: <https://render.com/docs/blueprint-spec>
- Vercel pricing: <https://vercel.com/pricing>
- Neon pricing: <https://neon.com/pricing>
- Neon connection pooling: <https://neon.com/docs/connect/connection-pooling>
- Upstash Redis pricing: <https://upstash.com/pricing/redis>
