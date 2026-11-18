# OCI Always Free Deployment Guide

Status: **repository preparation and validation complete; no OCI resources
provisioned and no production cutover performed.**

The backend target is one Oracle Cloud Always Free ARM64 VM running Docker
Compose. The Vercel frontend and the existing Moodle installation are not moved.
Railway configuration remains in the repository only for rollback/fallback.

## 0. Owner-confirmed constraints

- The application domain is `skillupactionafrica.co.ke`. DNS is managed through
  HostAfrica/cPanel. **Do not change DNS without explicit approval.**
- `skillupafrica.co.ke` (Moodle) and `skillupactionafrica.co.ke` (application)
  are different domains. Never substitute one for the other.
- OCI tenancy and A1 capacity are not confirmed. Do not provision resources or
  incur costs until the owner approves a provider and a resource estimate.
- The Compose stack is provider-neutral and can run on another Linux host with
  Docker, a persistent disk, and public `80`/`443`. See
  [`hosting-options.md`](hosting-options.md).
- Local development data may be used for staging/testing only. It is **not**
  authoritative production data and must not be presented as a production
  export.
- No production ACME certificate may be requested until an authorized ACME
  contact email is supplied.
- Google OAuth must remain disabled (empty client id/secret) until credentials
  and the callback URL are approved. The prepared callback is
  `https://api.skillupactionafrica.co.ke/api/v1/auth/google/callback`.
- Existing Moodle data and publishing records must not be overwritten,
  migrated, or deleted.

The complete approval gate list is in
[`production-readiness.md`](production-readiness.md).

## 1. What is deployed

| Component | Image | Exposure | Persistence |
| --- | --- | --- | --- |
| Caddy | `caddy:2-alpine` | host `80`, `443`, `443/udp` | `deploy/oci/data/caddy/` |
| API | `backend/Dockerfile` | private `api:8000` | `deploy/oci/data/storage/` |
| Ingestion worker | same API image | private | same storage bind mount |
| Content worker | same API image | private | database/Redis only |
| PostgreSQL | `postgres:17-alpine` | private `postgres:5432` | `deploy/oci/data/postgres/` |
| Redis | `redis:8-alpine` | private `redis:6379` | `deploy/oci/data/redis/` |
| Migration job | same API image | one-shot | none |

Caddy is the only publicly reachable container. Do not publish PostgreSQL,
Redis, or the API through OCI security lists, NSGs, or Compose ports.

The Compose file uses two networks:

- `edge`: Caddy and the API/workers that need outbound AI/Moodle access.
- `backend`: internal network for PostgreSQL and Redis.

## 2. Manual prerequisites

These actions require account access and cannot be performed from the
repository:

1. OCI tenancy with Always Free eligibility and MFA, or approval to use an
   alternative Docker host.
2. Permission to create a VCN, subnet, internet gateway, security list/NSG,
   and a `VM.Standard.A1.Flex` instance, or equivalent network on another
   provider.
3. The public SSH key for the deployment user. Never copy the private key to
   the server or into the repository.
4. DNS access for `skillupactionafrica.co.ke` through HostAfrica/cPanel.
   Approval is required before adding or changing any `api` record.
5. The authoritative source database and upload storage, if one exists under
   another account/provider. Local development data is staging-only.
6. An authorized ACME contact email for Caddy. Until supplied, do not request a
   production certificate.
7. Google OAuth credentials and explicit approval of the callback URL only if
   Google sign-in is to be enabled. Otherwise leave the client id/secret empty.

## 3. Create the OCI network and VM

Use the OCI Console. Do not create paid load balancers, NAT gateways, extra
block volumes, or larger shapes.

### 3.1 VCN

1. Region: choose the tenancy home region.
2. Create a VCN with a public subnet, for example `10.0.0.0/24`.
3. Attach an internet gateway and a route rule `0.0.0.0/0 -> internet gateway`.
4. Security list or NSG ingress:
   - TCP `22` from the administrator's public IP only, if practical.
   - TCP `80` from `0.0.0.0/0` (and `::/0` if IPv6 is used).
   - TCP `443` from `0.0.0.0/0` (and `::/0` if IPv6 is used).
   - No ingress for `5432`, `6379`, or `8000`.
5. Egress: allow outbound HTTPS for AI providers, Moodle, package updates, and
   ACME.

### 3.2 Instance

1. Shape: `VM.Standard.A1.Flex`.
2. OCPUs: `2`; memory: `12 GB`. This is the Always Free Ampere envelope.
3. Image: Ubuntu LTS ARM64 (24.04 or 22.04).
4. Boot volume: 50–100 GB. Keep all block storage at or below 200 GB.
5. Assign a public IPv4 address.
6. Add the deployment user's public SSH key. Disable password SSH after the
   key is confirmed working.
7. If A1 capacity is unavailable, try another availability domain or wait.
   Do not switch to a paid shape without approval.

Record the public IPv4 address and the SSH user (`ubuntu` on OCI Ubuntu
images). Do not put the private key in this repository.

## 4. DNS strategy

The production hostname is `api.skillupactionafrica.co.ke`.

- DNS is managed through HostAfrica/cPanel. Do not add, remove, or change any
  record without the owner's explicit approval.
- Frontend records for `skillupactionafrica.co.ke` and `www` are already
  attached to Vercel and must not be changed for this migration.
- Add only an `api` A record pointing to the OCI public IPv4 address when the
  stack is verified and the owner has approved the change.
- Do not change nameservers, MX, SPF, DKIM, DMARC, or any record under
  `skillupafrica.co.ke` / `elearning.skillupafrica.co.ke`.
- Use a low TTL (for example 300 seconds) during cutover.
- Remove any old `api` CNAME before adding the A record; a name cannot have a
  CNAME and an A record at the same time.
- Caddy needs public DNS plus inbound 80/443 to issue the certificate.

If a temporary hostname such as `api-staging.skillupactionafrica.co.ke` is
available, use it to verify TLS before changing `api`. Otherwise, use
`healthcheck.sh --local` on the VM and defer public TLS testing until cutover.

## 5. Bootstrap the host

Clone or copy the repository to `/opt/ai-course-engine`:

```bash
sudo mkdir -p /opt/ai-course-engine
sudo chown "$USER":"$USER" /opt/ai-course-engine
git clone https://github.com/jecintamuhia/ai-course-engine.git /opt/ai-course-engine
cd /opt/ai-course-engine
```

If the repository already exists, use `git pull --ff-only`; do not reset or
clean a server working tree with uncommitted changes.

Run the one-time bootstrap as root:

```bash
sudo bash deploy/oci/bootstrap.sh
```

It installs Docker Engine/Compose, UFW, fail2ban, chrony, unattended upgrades,
bounded Docker log rotation, and creates the persistent data directories with
the UIDs used by the official Postgres and Redis images.

After it completes, log out and back in so the deployment user receives Docker
group membership. Verify:

```bash
docker version
docker compose version
sudo ufw status
systemctl is-active docker
```

Docker-published ports bypass UFW. The Compose file is deliberately the only
thing allowed to publish ports, and only Caddy publishes `80`/`443`.

## 6. Create the production environment file

```bash
cd /opt/ai-course-engine/deploy/oci
cp .env.production.example .env.production
chmod 600 .env.production
```

Edit every `CHANGE_ME` value. Generate URL-safe secrets with:

```bash
openssl rand -hex 32
```

At minimum:

- `CADDY_DOMAIN=api.skillupactionafrica.co.ke`
- `ACME_EMAIL`: a monitored mailbox.
- `POSTGRES_PASSWORD` and `DATABASE_URL`: use the **same** password. The
  template uses hex so no URL encoding is needed.
- `SECRET_KEY`: a random 64+ character value. Rotating it invalidates existing
  access tokens.
- `OPENROUTER_API_KEY` and the approved `OPENROUTER_MODEL`.
- `MOODLE_TOKEN`: the existing production Moodle token. Never commit or print
  it. `MOODLE_URL` remains `https://elearning.skillupafrica.co.ke`.
- `CORS_ORIGINS` and `ALLOWED_HOSTS` as JSON arrays on one line.
- Google OAuth values only if Google sign-in is enabled. The redirect URI must
  exactly match Google Cloud:
  `https://api.skillupactionafrica.co.ke/api/v1/auth/google/callback`.
- `RUN_INGESTION_WORKER=false`; the OCI stack runs the ingestion worker as its
  own service.

Validate the environment without printing any values:

```bash
python3 validate_env.py
```

This checks required keys, placeholders, secret length, HTTPS URLs, CORS,
database URL consistency, Moodle pairing, AI provider keys, the prepared
Google callback, and `.env.production` permissions. It intentionally fails
until the owner-approved ACME email, Moodle token, AI key, and domain values
are present. Do not fill an approval-gated value merely to make validation
pass.

If the script is unavailable, a quick placeholder check is:

```bash
grep -n 'CHANGE_ME' .env.production
```

Expected: no output. Do not paste the full environment file or
`docker compose config` output into chat, tickets, or logs; resolved Compose
output contains secrets.

Validate the Compose and Caddy configuration without printing values:

```bash
docker compose --env-file .env.production -f compose.yaml config >/dev/null
docker run --rm --env-file .env.production \
  -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Caddy validation may log a failed active health check to `api:8000` because the
stack is not running yet. `Valid configuration` is the result that matters.

The Compose stack has also been smoke-tested locally with the current image:
PostgreSQL/Redis health, the one-shot migration, API readiness, auth methods,
both workers, and a local-Caddy HTTPS reverse proxy all passed. That test used
disposable data and did not touch production.

A disposable backup/restore round trip also passed using the same
`pg_dump -Fc`, `pg_restore --clean`, storage tar, migration, and API readiness
sequence as the scripts. The `restore.sh` root guard and ownership changes must
still be exercised on the Linux VM; they cannot be validated on Windows.

## 7. Data migration

### 7.1 If an authoritative source exists

Do not write to the source or the OCI target while taking the final export.

1. Record the source PostgreSQL version, extensions, database size, Alembic
   head, and per-table row counts.
2. Create a custom-format dump:

   ```bash
   pg_dump "$SOURCE_DATABASE_URL" -Fc -f postgres-source.dump
   ```

   Use a source credentials mechanism that does not put the password in shell
   history. Prefer `.pgpass` or a temporary `PGPASSWORD` environment variable
   set without echoing it.
3. Export the uploaded documents from the source storage volume using the
   provider's supported method. The path may be `/app/storage/documents` or a
   provider-specific mount; preserve the file names and relative layout.
4. Transfer both files to the VM over SSH. Example only; substitute real paths:

   ```bash
   scp postgres-source.dump storage-source.tar.gz \
     ubuntu@OCI_PUBLIC_IP:/opt/ai-course-engine/deploy/oci/data/backups/
   ```

5. On the VM, start only the database and cache first:

   ```bash
   cd /opt/ai-course-engine/deploy/oci
   docker compose --env-file .env.production -f compose.yaml up -d postgres redis
   ```

6. Restore both artifacts. `SKIP_BACKUP=1` is appropriate for a new empty
   target; omit it when restoring over an existing target so a safety backup is
   taken first.

   ```bash
   SKIP_BACKUP=1 bash restore.sh \
     data/backups/postgres-source.dump \
     data/backups/storage-source.tar.gz
   ```

7. Verify row counts, constraints, Alembic head, and document-file counts before
   allowing users in. Do not claim migration success until these match the
   source or the differences are explained and approved.

### 7.2 If no source production data exists

This is the current repository-side situation. Deploy an empty production
database, run migrations, and create the first administrator. Do not describe
this as a data migration.

Local development data may be imported into a **disposable staging** target to
exercise this procedure, but it is not authoritative production data. Never
restore that data over an existing production target. Take a fresh backup,
verify row and file counts, and record the source explicitly.

```bash
cd /opt/ai-course-engine/deploy/oci
docker compose --env-file .env.production -f compose.yaml up -d --build
docker compose --env-file .env.production -f compose.yaml ps -a
```

The one-shot `migrate` service must exit with status `0`. The API waits for it
to complete. If it fails, inspect:

```bash
docker compose --env-file .env.production -f compose.yaml logs migrate
```

### 7.3 Create the first administrator

After the API is healthy:

```bash
docker compose --env-file .env.production -f compose.yaml exec api \
  python scripts/create_admin.py \
  --email admin@example.com \
  --full-name "Administrator" \
  --role admin
```

Use the real administrator email. The password is prompted without echo. Do
not put a password on the command line or in shell history.

## 8. Verification before cutover

Run the local checks:

```bash
cd /opt/ai-course-engine/deploy/oci
bash healthcheck.sh --local
```

Expected:

- `postgres` and `redis` healthy.
- `api` healthy.
- `ingestion-worker` and `content-worker` running.
- `/health/ready` returns `{"status":"ready"}` inside the API container.
- `/api/v1/health` returns `{"status":"ok"}`.

Inspect the stack and logs without printing secrets:

```bash
docker compose --env-file .env.production -f compose.yaml ps
docker compose --env-file .env.production -f compose.yaml logs --tail=100 api
docker compose --env-file .env.production -f compose.yaml logs --tail=100 caddy
```

Additional gates:

- PostgreSQL and Redis are not reachable from another host.
- The VM has no swap pressure and enough free disk.
- Both workers reconnect after a restart.
- Registration/login works with a test learner on the empty stack, or with the
  real admin after a data migration.
- Google OAuth works only if configured with the exact callback URL.
- Upload and PDF extraction work; inspect the ingestion worker logs.
- Curriculum/lesson generation works; inspect the content worker logs.
- `GET /api/v1/moodle/preflight` succeeds read-only after admin login. Do not
  publish a course to production Moodle without explicit approval.
- The Vercel frontend can reach the API after DNS points at the VM and CORS
  succeeds from `https://skillupactionafrica.co.ke`.

## 9. DNS cutover

Only after the verification gates pass:

1. Take a final backup while writes are paused.
2. Confirm `api.skillupactionafrica.co.ke` has no CNAME.
3. Add/replace the `api` A record with the OCI public IPv4 address.
4. Wait for the previous TTL and verify public resolution.
5. Watch certificate issuance:

   ```bash
   cd /opt/ai-course-engine/deploy/oci
   docker compose --env-file .env.production -f compose.yaml logs -f caddy
   ```

6. Run public checks:

   ```bash
   bash healthcheck.sh
   curl -fsS https://api.skillupactionafrica.co.ke/health/ready
   curl -fsS https://api.skillupactionafrica.co.ke/api/v1/health
   ```

7. Open the Vercel frontend, sign in, upload a small document, and confirm the
   worker completes it. Use permitted test content only.
8. Keep the previous backend and its data untouched for the agreed rollback
   window. Do not delete Railway resources, source backups, or the OCI VM.

If a temporary staging hostname was used, change `CADDY_DOMAIN` in
`.env.production`, then recreate Caddy:

```bash
docker compose --env-file .env.production -f compose.yaml up -d caddy
```

Changing the domain requires Caddy to obtain a new certificate.

## 10. Rollback

Rollback is a DNS and traffic decision; it must not destroy data.

1. If `api` previously pointed at another backend, restore the exact old DNS
   record. If there was no previous API record, remove the new record and
   coordinate with the frontend owner; do not invent a fallback host.
2. Leave the OCI VM and its database/storage running long enough to inspect the
   failure and recover.
3. Do not run `docker compose down -v`; this stack uses bind mounts, but avoid
   destructive volume commands regardless.
4. Keep the Railway configuration files and any Railway resources for the
   agreed window.
5. Do not delete source dumps or offsite backups until the migration is signed
   off.
6. After rollback, fix the issue, verify locally with `healthcheck.sh --local`,
   and repeat the cutover.

If only the application is broken but DNS is already cut over, it is usually
faster to roll back the API image or configuration than to change DNS back.

## 11. Security checklist

- OCI security list: inbound `22` restricted; `80`/`443` public; no `5432`,
  `6379`, or `8000`.
- UFW: deny incoming by default; allow SSH, 80, 443.
- SSH: key-only; password authentication disabled after verification.
- Secrets: `.env.production` mode `600`, never committed or logged; `SECRET_KEY`
  is stable and private.
- Containers: application processes run as `appuser` (uid 1000); Compose sets
  `no-new-privileges`.
- Database/cache: private Docker networks; no host ports.
- TLS: Caddy automatic HTTPS; HSTS and security headers configured.
- Upload limit: Caddy caps request bodies at 55 MB; the application remains at
  50 MB.
- Logs: Docker `json-file` rotation 10 MB × 5; Caddy logs JSON to stdout.
- Host: unattended upgrades, fail2ban, chrony/UTC, bounded Docker logs.
- Backups: mode `0700`, checksummed, copied off the VM, and restore-tested.
- Rate limiting is **not** enabled in stock Caddy. Add a rate-limit module only
  as a separate, reviewed change; do not claim it exists today.

## 12. Cost and Always Free boundaries

Expected recurring cost is **$0** only while all usage remains inside the
Always Free envelope:

- 2 OCPUs / 12 GB RAM of Ampere A1 compute.
- 200 GB total block storage (boot plus block volumes).
- 20 GB Object Storage and 50,000 API requests/month in an Always Free-only
  tenancy.
- 10 TB outbound data transfer per month.
- No managed PostgreSQL, load balancer, NAT gateway, or extra paid networking.

A 50–100 GB boot volume leaves headroom for backups inside the block-storage
allowance. Copy backups off the VM within the Object Storage allowance or to
another owned machine; exceeding either allowance can create charges.

Do not add additional OCPUs, memory, block volumes, paid load balancers, NAT
gateways, or paid database services without explicit approval. Verify actual
usage and billing in the OCI Console; this repository cannot prove a $0 bill.

## 13. Operations

Backup/restore, updates, monitoring, and troubleshooting are in
[`docs/oci-operations.md`](oci-operations.md). The original migration audit is
in [`docs/oci-migration-plan.md`](oci-migration-plan.md).
