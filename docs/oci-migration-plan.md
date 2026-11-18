# OCI Always Free Migration Plan

Status: **repository preparation and local validation complete**. No OCI
resources have been provisioned and no production cutover has occurred.
Production approval gates are tracked in
[`production-readiness.md`](production-readiness.md); hosting choices are in
[`hosting-options.md`](hosting-options.md).

Deployment instructions: [`docs/oci-deployment.md`](oci-deployment.md).
Routine operations: [`docs/oci-operations.md`](oci-operations.md).

A disposable local round trip verified PostgreSQL dump/restore, storage
archive/restore, migrations, and API readiness. The Linux-only `backup.sh` /
`restore.sh` wrappers still need to be run on the target VM before cutover.

## 1. Audit findings

| Area | Current implementation | OCI implication |
| --- | --- | --- |
| Framework | FastAPI, `app.main:app` | Keep unchanged |
| Python | `>=3.12`; image uses `python:3.12-slim` | Multi-arch image includes `linux/arm64/v8` |
| Dependencies | `requirements/base.txt` and `requirements/production.txt` | Must verify ARM64 wheels at image build time |
| Docker image | `backend/Dockerfile`; root entrypoint prepares storage then drops to `appuser` | Reuse image; Compose sets `UPLOAD_DIR=/app/storage/documents` |
| Local Compose | `backend/docker-compose.yml` uses bind-mounted source, `--reload`, exposed Postgres/Redis | Development only; do not use for OCI |
| Database | PostgreSQL 17, async SQLAlchemy + asyncpg, Alembic head `9d1e4c7a2b30` | Run `alembic upgrade head` as a one-shot Compose service |
| Redis | Redis 8, AOF, custom reliable queues using lists and sorted sets | Persistent volume required; never publish port 6379 |
| Ingestion worker | `app.workers.ingestion_worker`, consumes `ingestion:jobs:*`, handles SIGTERM | Needs same storage volume as API; graceful stop |
| Content worker | `app.workers.content_worker`, consumes `content_generation:jobs:*` | No storage volume required; DB/Redis only |
| Analysis/planning workers | Zero-byte placeholder files | Do not deploy |
| Upload storage | Local filesystem, path stored in `documents.storage_path` | Bind mount must keep the **same absolute path** `/app/storage/documents` |
| Auth | JWT; self-registration creates learners only; Google OAuth code flow | Preserve `SECRET_KEY`; Google callback must remain the API HTTPS URL |
| CORS | Explicit origins from `CORS_ORIGINS`; wildcard rejected | Keep apex + `www` Vercel origins |
| Moodle | REST web services via `MOODLE_URL` + `MOODLE_TOKEN` | OCI needs outbound HTTPS only; no inbound Moodle access |
| Frontend | Vercel project `skillup-action-africa` | No rebuild needed; API base already `https://api.skillupactionafrica.co.ke/api/v1` |
| Railway API config | `backend/railway.toml` | Keep for rollback; not used on OCI |
| Railway worker config | `backend/railway.content-worker.toml` | Keep for rollback; not used on OCI |
| Railway co-located ingestion | `backend/scripts/start_api.sh` | OCI runs ingestion as its own Compose service |
| Railway volume workaround | Entrypoint chowns volume, `RUN_INGESTION_WORKER` | Entrypoint is provider-neutral; OCI uses a bind mount |

### Critical deployment finding

The currently authenticated Railway account has **no project containing this
application**. `railway list` shows only `<claude-tradingview-mcp-trading>`,
`railway status` reports no linked project, and
`api.skillupactionafrica.co.ke` does not resolve. The running stack on this
machine is the development Compose stack, not a Railway production backend.

Consequences:

- There is no verified Railway production database to export from this account.
- The local development database is empty (all application tables report zero
  rows; size 18 MB; Alembic head `9d1e4c7a2b30`).
- This work therefore prepares and validates the OCI production target. It
  cannot truthfully claim a production data migration until a source database
  and/or OCI account access is supplied.

## 2. Target architecture

One Always Free `VM.Standard.A1.Flex` instance, 2 OCPUs / 12 GB RAM, Ubuntu LTS
ARM64, running Docker Compose:

```text
Internet
  |
  | 443/80
  v
Caddy (TLS, compression, security headers, JSON access logs)
  |
  | private Docker network
  v
api:8000  <---->  postgres:5432
  |                   ^
  |                   |
ingestion-worker -----+
  |
content-worker -------+
  |
redis:6379
```

- Caddy is the only service that publishes host ports (`80`, `443`).
- PostgreSQL and Redis publish no host ports.
- API, workers, and proxy use the internal Compose network.
- Bind-mounted data under
  `/opt/ai-course-engine/deploy/oci/data`:
  - `postgres/`
  - `redis/`
  - `storage/documents/`
  - `caddy/data/`, `caddy/config/`
  - `backups/`
- Containers use Docker's `json-file` logging with rotation.
- Application containers run as the existing non-root `appuser` after the
  entrypoint prepares the bind-mounted storage directory.

### Always Free envelope

Per Oracle documentation (2026):

- Ampere A1: first 1,500 OCPU-hours and 9,000 GB-hours per month; in an Always
  Free tenancy this is 2 OCPUs and 12 GB RAM total.
- Block Volume: 200 GB total combined boot and block volumes, five volume
  backups.
- Object Storage: 20 GB combined, 50,000 API requests/month (Always Free-only
  tenancy).
- Outbound data transfer: 10 TB/month.
- No Always Free managed PostgreSQL service is used; PostgreSQL runs inside
  the VM.
- No paid load balancer, NAT gateway, reserved public IP, or extra block
  volume is required.

Estimated recurring cost: **$0** while all usage stays inside the Always Free
limits. Any extra OCPU/RAM, block volume above 200 GB, paid Object Storage
usage, or paid network service would introduce a charge and must not be added
without approval.

## 3. Migration phases and gates

### Phase A — Repository and image preparation (complete)

1. Added `deploy/oci/compose.yaml`, `Caddyfile`, environment template,
   bootstrap script, backup/restore scripts, healthcheck script, and systemd
   timers.
2. Built the backend image for `linux/arm64` and verified
   `import app.main` under ARM64 emulation.
3. Validated the Compose model with a dummy environment file and validated the
   Caddyfile with `caddy validate`.
4. Kept all Railway configuration intact for rollback/fallback.

Validated locally on 2026-11-03:

- `docker compose config` accepted the stack (output deliberately not retained
  because resolved environment values may contain secrets).
- Caddy reported `Valid configuration`; its active upstream health check failed
  during validation only because the API was not running.
- ARM64 image built successfully and `app.main` imported successfully.
- Full local Compose smoke test passed: PostgreSQL and Redis healthy, Alembic
  exited `0`, API `/health/ready` and `/api/v1/auth/methods` returned valid
  responses, and both workers reported healthy. Caddy was also tested with a
  local `localhost` certificate and proxied `/health/ready` successfully with
  the configured security headers. Test containers, volumes, data, and images
  were removed afterward; no production data or services were touched.

### Phase B — OCI account and network

1. Create/confirm the OCI Always Free tenancy and home region.
2. Create a VCN with a public subnet, internet gateway, route table, and
   security list/NSG:
   - inbound 22/TCP from the administrator's public IP only;
   - inbound 80/TCP and 443/TCP from `0.0.0.0/0` and `::/0`;
   - no inbound 5432, 6379, or 8000.
3. Create a 2 OCPU / 12 GB A1 instance with Ubuntu LTS ARM64 and a 50–100 GB
   boot volume. Do not exceed 200 GB total block storage.
4. If OCI reports out-of-host-capacity, try another availability domain or
   wait; do not upgrade to paid capacity without approval.

### Phase C — Host bootstrap

1. SSH with the existing ED25519 key; password authentication is not used.
2. Run `deploy/oci/bootstrap.sh` as root/sudo.
3. Confirm Docker, Compose, UFW, fail2ban, log rotation, and UTC time.
4. Clone the repository to `/opt/ai-course-engine` or rsync it from the
   development machine.
5. Create `deploy/oci/.env.production` from the template, `chmod 600`, owned by
   the deployment user.

### Phase D — Database and storage

1. Obtain the authoritative source database URL and upload storage from the
   current provider. Because no Railway project exists under the inspected
   account, this is a manual access/ownership blocker.
2. Take a source `pg_dump -Fc` and copy the uploaded documents.
3. Record source PostgreSQL version, extensions, Alembic head, database size,
   and row counts.
4. Restore into the OCI PostgreSQL container and run `alembic upgrade head`.
5. Verify row counts and constraints before starting the API.
6. Test an actual restore into a temporary database or container.

### Phase E — Application deployment

1. `docker compose --env-file .env.production up -d postgres redis`
2. Run the one-shot `migrate` service.
3. Start `api`, `ingestion-worker`, and `content-worker`.
4. Start Caddy after the API is ready.
5. Test over a temporary HTTPS hostname before touching the production `api`
   DNS record. If a temporary hostname is unavailable, test HTTP on the VM's
   public IP only for readiness and keep production DNS unchanged.

### Phase F — Verification

Required before DNS cutover:

- `/health/ready` returns `{"status":"ready"}`.
- `/api/v1/health` returns `{"status":"ok"}`.
- PostgreSQL and Redis are healthy and not publicly reachable.
- Both workers are running and reconnect after a restart.
- User registration/login and Google OAuth (using the correct callback URL).
- Upload, PDF extraction, analysis, curriculum generation, lesson generation,
  lecturer approval, and Moodle preflight.
- Moodle publishing only after explicit approval; no test publication to
  production Moodle.
- Frontend on Vercel reaches the new API and CORS succeeds.
- Database row counts and relationships match the source.
- Backup and restore have been performed and verified.

### Phase G — Cutover and rollback

1. Keep the old backend and its database untouched.
2. Take a final source backup while writes are paused.
3. Apply the final incremental restore.
4. Change only the `api.skillupactionafrica.co.ke` DNS record to the OCI public
   IP (A record), or CNAME if an OCI load balancer is used.
5. Verify TLS issuance, health, login, upload, and Moodle connectivity.
6. Keep the old deployment for at least the agreed rollback window.
7. Roll back by restoring the previous DNS record; do not delete Railway
   resources or backups.

## 4. Manual blockers

These cannot be completed from the repository:

1. OCI account/tenancy access and MFA; no OCI CLI config or credentials exist
   on this machine.
2. VM provisioning and Always Free capacity availability.
3. DNS access for `skillupactionafrica.co.ke` through HostAfrica/cPanel.
   Approval is required before adding or changing any record; do not assume a
   nameserver or provider from incomplete public-resolution evidence.
4. Source production database and upload storage if they live under a different
   account/provider. Local development data is staging-only.
5. An authorized ACME contact email before requesting a production certificate.
6. Google OAuth credentials and callback approval, or an explicit decision to
   keep Google sign-in disabled.
7. Moodle URL/token and permission confirmation; preserve all Moodle data and
   publishing records.
6. An ACME contact email for Caddy.

## 5. Rollback position

Railway configuration files, the Vercel frontend, and all existing data are
left unchanged. No DNS change is made in this repository preparation. If the
OCI deployment fails, the previous backend/DNS can remain or be restored
without data loss.
