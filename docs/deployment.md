# Production Deployment Runbook

Status: **partially deployed**. The Vercel frontend is live; the backend target
is now Oracle Cloud Always Free, not Railway. This runbook keeps the Railway
material as a fallback and points to the active OCI guide. Items marked
**external blocker** require a human with account or DNS access.

> **Backend target changed (2026-11-03):** use
> [`docs/oci-deployment.md`](oci-deployment.md) for the active OCI Always Free
> Docker Compose deployment and [`docs/oci-operations.md`](oci-operations.md)
> for backup, restore, updates, and monitoring. The Railway sections below are
> retained only for rollback/fallback and must not be used to create new
> production resources without explicit approval.
>
> Current launch gates and evidence are in
> [`production-readiness.md`](production-readiness.md); hosting estimates are in
> [`hosting-options.md`](hosting-options.md).

## Current deployment state (2026-11-03)

| Item | State |
| --- | --- |
| Vercel project | `skillup-action-africa` created, linked, and connected to `github.com/jecintamuhia/ai-course-engine` |
| Vercel production URL | `https://skillup-action-africa.vercel.app` (verified 200, SPA deep links, API base baked into JS) |
| Custom domains attached in Vercel | `skillupactionafrica.co.ke`, `www.skillupactionafrica.co.ke` |
| DNS records applied | No. The owner states DNS is managed through HostAfrica/cPanel. Do not change the zone without explicit approval; confirm the authoritative nameservers in that account before adding records. |
| Railway project | Not created. Project creation is blocked by the free-plan resource limit; retained only as fallback. |
| OCI target | Repository stack prepared and validated locally; no OCI resources provisioned yet. |
| API | Not deployed. |
| Moodle | Untouched; read-only preflight previously passed. |

## Target topology

| Surface | Host | Platform |
| --- | --- | --- |
| Authoring and learner SPA | `https://skillupactionafrica.co.ke` | Vercel |
| FastAPI backend | `https://api.skillupactionafrica.co.ke` | OCI Always Free VM + Caddy |
| PostgreSQL | Private Docker Compose service | OCI VM |
| Redis | Private Docker Compose service | OCI VM |
| Existing Moodle | `https://elearning.skillupafrica.co.ke` | Existing HostAfrica server, **do not change** |

The Moodle hostname is `skillupafrica.co.ke` (no "action") and is a
different registrable domain from the application. Do not rename, migrate,
or re-point it as part of this deployment.

## OCI target

The active deployment stack lives in `deploy/oci/`:

- `compose.yaml`: Caddy, API, PostgreSQL, Redis, ingestion worker, content
  worker, and a one-shot migration service.
- Caddy publishes only `80`/`443`; PostgreSQL, Redis, and the API have no host
  ports.
- The API and ingestion worker share the `data/storage` bind mount; the
  content worker does not mount storage.
- `bootstrap.sh` prepares Ubuntu, Docker, UFW, fail2ban, and data directories.
- `backup.sh`, `restore.sh`, and `healthcheck.sh` cover operations.

See [`docs/oci-deployment.md`](oci-deployment.md) for provisioning, data
migration, DNS cutover, rollback, security, and cost boundaries. Do not use the
Railway setup below unless the OCI migration is explicitly abandoned.

## Railway fallback architecture decisions

The following bullets describe the Railway fallback only. They are not the
current target.

- The API and the ingestion worker run in the **same** Railway service.
  `backend/scripts/start_api.sh` starts the worker in the background and then
  `exec`s uvicorn. Railway volumes cannot be shared between services, and the
  worker must read the PDFs the API writes to `/app/storage`.
- The content worker runs as a **separate** service. It only needs PostgreSQL,
  Redis, the LLM key, and Moodle credentials; it must not mount a volume.
- Only one API replica may run while the volume is attached. Railway does not
  support volumes with multiple replicas.
- `backend/docker-entrypoint.sh` starts as root only to prepare and `chown` the
  mounted storage path, then drops to `appuser` (uid 1000) with `gosu`.
- The frontend is built by Vercel and served from Vercel. The Docker image does
  not copy the SPA; FastAPI's optional static mount is for local development.
- Alembic is the schema authority. Migrations are additive. Do not use
  `alembic downgrade` against production without explicit approval.

## Repository settings

| Setting | Value |
| --- | --- |
| Railway service root directory | `backend` for both the API and content worker |
| Railway Dockerfile | `Dockerfile` (relative to the service root) |
| Railway build context | `backend` (Railway uses the service root) |
| API config-as-code path | `/backend/railway.toml` |
| Content-worker config-as-code path | `/backend/railway.content-worker.toml` |
| Vercel root directory | `backend/frontend` |
| Vercel framework | Vite |
| Vercel install command | `npm ci` |
| Vercel build command | `npm run build` |
| Vercel output directory | `dist` |
| Package manager | npm (`package-lock.json` is authoritative) |
| OCI Compose file | `deploy/oci/compose.yaml` |
| OCI deployment guide | `docs/oci-deployment.md` |
| OCI operations guide | `docs/oci-operations.md` |

Do **not** set the Railway service root to the repository root. Railway always
uses the service root as the Docker build context, so `backend/Dockerfile`'s
`COPY requirements ...` and `COPY app ...` instructions only work when the
context is `backend`. There is intentionally no root `railway.toml`.

`backend/railway.toml`, `backend/railway.content-worker.toml`, and
`backend/frontend/vercel.json` are checked in. Railway's config-as-code support
is deprecated for services created after the deprecation date (legacy services
keep working until 2026-12-01). If the dashboard ignores the config file,
configure the build, start command, pre-deploy command, and healthcheck
manually using the values below.

## Environment variables (Railway fallback)

The active OCI template is `deploy/oci/.env.production.example`. The values
below are retained as the Railway fallback reference.

Set these in the Railway **API** service. Never commit real values, and never
place secrets in Vercel or in the repository.

### Required

| Variable | Value / note |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `SECRET_KEY` | Random 64+ character value. Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Rotating it invalidates all access tokens. |
| `DATABASE_URL` | Railway PostgreSQL reference, e.g. `${{Postgres.DATABASE_URL}}`. `postgres://` and `postgresql://` are normalised to `postgresql+asyncpg://` automatically. |
| `REDIS_URL` | Railway Redis reference, e.g. `${{Redis.REDIS_URL}}`. |
| `AI_PROVIDER` | `openrouter` |
| `OPENROUTER_API_KEY` | Production key. Empty or missing fails application startup. |
| `OPENROUTER_MODEL` | Approved production model id. |
| `CORS_ORIGINS` | JSON array: `["https://skillupactionafrica.co.ke","https://www.skillupactionafrica.co.ke"]` |
| `FRONTEND_URL` | `https://skillupactionafrica.co.ke` |
| `ALLOWED_HOSTS` | JSON array: `["api.skillupactionafrica.co.ke","skillupactionafrica.co.ke","localhost","127.0.0.1"]` |
| `UPLOAD_DIR` | `/app/storage/documents` |
| `MOODLE_URL` | `https://elearning.skillupafrica.co.ke` |
| `MOODLE_TOKEN` | Existing Moodle web-service token. Treat as a secret. |
| `MOODLE_COURSE_CATEGORY_ID` | `1` (the verified target category) |
| `AUTH_REGISTRATION_ENABLED` | `true` to allow learner self-registration |
| `LEARNER_DESTINATION` | `/learn` |

### Recommended

| Variable | Value / note |
| --- | --- |
| `LOG_JSON` | `true` in production |
| `LOG_LEVEL` | `INFO` |
| `RUN_INGESTION_WORKER` | `true` on the API service (default) |
| `DATABASE_POOL_SIZE` | `10` |
| `DATABASE_MAX_OVERFLOW` | `20` |
| `OPENROUTER_TIMEOUT_SECONDS` | `300` |
| `YOUTUBE_API_KEY` | Optional; required only for video discovery |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Optional; set both or neither |
| `GOOGLE_OAUTH_REDIRECT_URI` | `https://api.skillupactionafrica.co.ke/api/v1/auth/google/callback` when Google sign-in is enabled |

The content worker needs the same `DATABASE_URL`, `REDIS_URL`, AI, and Moodle
variables. It does not need `UPLOAD_DIR`, a volume, or
`RUN_INGESTION_WORKER`.

List settings (`CORS_ORIGINS`, `ALLOWED_HOSTS`,
`AUTH_REGISTRATION_ALLOWED_DOMAINS`) are parsed as JSON. Enter them on one line
exactly as shown; a bare comma-separated string is not valid.

## Railway fallback setup

Do not follow this section for the active OCI deployment. Use it only if the
OCI migration is explicitly abandoned.

1. Create a Railway project from the GitHub repository.
2. Add the PostgreSQL and Redis plugins. Note the service names used in the
   reference variables.
3. Create the API service from the GitHub repository, set its root directory to
   `backend`, and confirm the builder uses `Dockerfile`. Set the config-as-code
   path to `/backend/railway.toml` if the dashboard asks for one.
4. Set the API environment variables above.
5. Add a volume mounted at `/app/storage` to the API service.
6. Set one replica. The entrypoint will make the mount writable by `appuser`.
7. Configure:
   - Start command: `sh /app/scripts/start_api.sh`
   - Pre-deploy command: `alembic upgrade head`
   - Healthcheck path: `/health/ready`
   - Healthcheck timeout: `120` seconds
   - Restart policy: `ON_FAILURE`, 10 retries
8. Create the content-worker service from the same repository and `backend`
   root directory, using the same Dockerfile, with no volume. Set its
   config-as-code path to `/backend/railway.content-worker.toml`, or configure:
   - Start command: `sh -c 'exec python -m app.workers.content_worker'`
   - One replica
   - Same database, Redis, AI, and Moodle variables
9. Deploy the API first so migrations run, then deploy the content worker.
10. Add the custom domain `api.skillupactionafrica.co.ke` to the API service.
    Copy the exact CNAME target and any verification TXT value from Railway.

The API will fail to start if `OPENROUTER_API_KEY` is empty while
`AI_PROVIDER=openrouter`. That is intentional; do not work around it by
switching providers in production.

## Vercel setup

1. Import the GitHub repository.
2. Set the root directory to `backend/frontend`.
3. Confirm the Vite preset, `npm ci`, `npm run build`, and output directory
   `dist` (also encoded in `backend/frontend/vercel.json`).
4. Add the production environment variable:
   - `VITE_API_BASE_URL=https://api.skillupactionafrica.co.ke/api/v1`
5. Deploy. Vite inlines this value at build time, so changing it requires a new
   deployment.
6. Add `skillupactionafrica.co.ke` and `www.skillupactionafrica.co.ke` as
   Vercel domains. Copy the exact A/CNAME values Vercel displays.

## HostAfrica DNS

**External blocker:** `skillupactionafrica.co.ke`, `www`, and `api` currently
return NXDOMAIN. Before adding application records, confirm in HostAfrica that
the domain is registered, the zone exists, and the intended nameservers are
delegated. Do not change nameservers until the current mail and Moodle records
have been inventoried.

In the HostAfrica/cPanel DNS zone editor for `skillupactionafrica.co.ke`, add
only the records the provider dashboards generate. The values below are the
ones Vercel returned for the deployed project on 2026-11-03:

| Name | Type | Value |
| --- | --- | --- |
| `@` | A | `216.198.79.1` |
| `@` | A | `64.29.17.1` |
| `www` | CNAME | `5665c4a17d1ea958.vercel-dns-017.com.` |
| `api` | A | OCI public IPv4 address, after OCI verification and cutover |
| Verification names | TXT | Exact values from Vercel, if requested |

The OCI target uses a direct A record to the VM. Do not create a CNAME for
`api` at the same time. If Railway fallback is used, replace the A record with
the exact CNAME target from Railway instead. Do not invent either value.

`76.76.21.21` and `cname.vercel-dns.com.` are Vercel's lower-ranked fallback
values. Prefer the project-specific values above. Re-run
`vercel domains verify skillupactionafrica.co.ke` and
`vercel domains verify www.skillupactionafrica.co.ke` after applying records.

Rules:

- Do not invent IP addresses or CNAME targets. Copy them from the dashboards.
- Do not touch MX, SPF, DKIM, DMARC, or any record under
  `skillupafrica.co.ke` / `elearning.skillupafrica.co.ke`.
- Keep TTLs at the provider default unless there is a reason to lower them.
- Allow time for propagation before treating DNS failures as application bugs.

## Moodle preservation

The existing Moodle site is production and must remain untouched by this
deployment except for normal application API calls after explicit approval.

- Do **not** modify the Moodle database, plugin files, configuration, courses,
  users, enrolments, SSL, or DNS.
- Do **not** publish test courses. The read-only preflight already passed
  against the live site: 9 functions exposed, all 8 required functions
  available, category id `1` found.
- Keep `MOODLE_TOKEN` in the provider secret store only: Railway variables for
  the fallback, or `deploy/oci/.env.production` mode `600` on OCI. Never print
  it in logs, tickets, chat, or documentation.
- `GET /api/v1/moodle/preflight` is read-only and is the correct post-deploy
  check. Publishing is a separate, explicit action.

## Railway fallback deploy sequence

The active OCI sequence is in [`docs/oci-deployment.md`](oci-deployment.md).
The steps below apply only to the Railway fallback.

1. Confirm the domain/zone issue with HostAfrica (external blocker).
2. Create Railway plugins and the API service; add the volume and variables.
3. Deploy the API. Confirm the pre-deploy migration succeeds.
4. Create and deploy the content-worker service.
5. Import the frontend into Vercel, set `VITE_API_BASE_URL`, deploy.
6. Attach custom domains in Vercel and Railway; copy DNS targets.
7. Add the DNS records at HostAfrica.
8. Run the verification gates below.
9. Bootstrap the first admin (see below).

## Post-deploy verification

Run these from a machine with public DNS access.

```bash
curl -fsS https://api.skillupactionafrica.co.ke/health/ready
# expected: {"status":"ready"}

curl -fsS https://api.skillupactionafrica.co.ke/api/v1/health
# expected: {"status":"ok"}

curl -fsS https://api.skillupactionafrica.co.ke/api/v1/auth/methods
# expected: JSON describing enabled sign-in methods

curl -fsSI https://skillupactionafrica.co.ke
# expected: HTTP 200 and an HTML content type
```

Then verify in the Railway fallback shell. For OCI, use
`deploy/oci/healthcheck.sh` and the checks in `docs/oci-deployment.md` instead.

```bash
alembic current
# expected head: 9d1e4c7a2b30

id
# expected: uid=1000(appuser)

ls -ld /app/storage/documents
# expected: owned by appuser, writable by appuser
```

Application checks:

- Sign in as an admin and open the Publish screen. Preflight must report ready.
- Confirm the browser console has no CORS errors against the API origin.
- Confirm self-registration creates a `student` only and lands on `/learn`.
- Confirm a lecturer sign-in lands on `/dashboard`.
- Confirm `https://skillupactionafrica.co.ke` deep links load the SPA rather
  than returning a Vercel 404.
- Do not upload a real textbook or publish to Moodle until the client approves
  the spend and the publish action.

## First administrator (Railway fallback)

For OCI, run the command from `docs/oci-deployment.md`. In the Railway fallback,
run inside the API service shell (working directory `/app`):

```bash
python scripts/create_admin.py --email admin@example.com --full-name "Administrator" --role admin
```

The password is prompted interactively. Avoid `--password` on the command line
because it can leak into shell history and logs. Never commit credentials or
the generated `.admin_credentials.txt`.

## Rollback

- OCI: see the dedicated rollback section in `docs/oci-deployment.md`. Keep the
  VM and data, restore the previous `api` DNS record, and do not run
  `docker compose down -v`.
- Railway fallback: redeploy the previous successful deployment. Migrations are
  additive; do not downgrade unless explicitly approved and backed up first.
- Vercel: promote the previous deployment.
- DNS: revert only the records added in this runbook. Do not touch unrelated
  records.
- If the ingestion worker enters a restart loop, check that the API has the
  storage mount and that `REDIS_URL` and `DATABASE_URL` are correct. The worker
  log line includes its exit status.

## Secrets and rotation

- Secrets live only in the active provider's secret store (Railway variables
  for fallback, or OCI `.env.production` mode `600`), plus Vercel's public
  `VITE_API_BASE_URL` (not a secret).
- If a token or key is exposed, rotate it at the provider and update the active
  deployment.
- Rotating `SECRET_KEY` signs out every user.
- Never print secret values in deployment logs, screenshots, or pull requests.
