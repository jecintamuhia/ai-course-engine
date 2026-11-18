# OCI Operations Guide

This guide covers the deployed Docker Compose stack under
`/opt/ai-course-engine/deploy/oci`. Deployment and cutover are in
[`docs/oci-deployment.md`](oci-deployment.md).

All commands below assume:

```bash
cd /opt/ai-course-engine/deploy/oci
```

## 1. Service layout

| Service | Expected state | Notes |
| --- | --- | --- |
| `caddy` | running, healthy | only public service |
| `api` | running, healthy | waits for `migrate` |
| `ingestion-worker` | running, healthy | shares API storage |
| `content-worker` | running, healthy | no storage volume |
| `postgres` | running, healthy | private network only |
| `redis` | running, healthy | private network only |
| `migrate` | exited `0` | one-shot Alembic migration |

Check:

```bash
docker compose --env-file .env.production -f compose.yaml ps -a
```

## 2. Backups

### 2.1 What is backed up

`backup.sh` creates a matched pair:

- PostgreSQL custom-format dump.
- Compressed archive of `data/storage` (uploaded documents).

Redis is not included. Redis AOF persists across normal restarts, but a restore
does not replay lost in-flight queue jobs. The database and document storage are
authoritative; re-run failed extraction/generation jobs from the application if
needed.

The database dump and storage archive are taken in sequence, not from a
single filesystem snapshot. For a fully consistent document snapshot, run the
backup during low activity or briefly stop the API and ingestion worker first.
A file uploaded between the dump and the tar is harmless (it is simply newer
than the database dump); avoid tarring a file that is actively being written.

### 2.2 Manual backup

```bash
sudo bash backup.sh
```

Files are written to `data/backups/` with mode `0700`, a timestamp, and a
`SHA256SUMS-*.txt` file. `BACKUP_RETENTION_DAYS` in `.env.production` controls
local retention (default 14 days).

Verify the checksum before copying:

```bash
cd data/backups
sha256sum -c SHA256SUMS-YYYYMMDDTHHMMSSZ.txt
```

Copy each pair off the VM to an owned destination. Do not commit backups to the
repository. If using OCI Object Storage, stay inside the 20 GB Always Free
allowance and use a lifecycle policy that deletes old backups.

### 2.3 Scheduled backup

Install the supplied units:

```bash
sudo cp systemd/ai-course-engine-backup.service /etc/systemd/system/
sudo cp systemd/ai-course-engine-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-course-engine-backup.timer
systemctl list-timers ai-course-engine-backup.timer
```

The timer runs daily at 02:30 local VM time (UTC is configured) with a small
random delay. Check the last run:

```bash
systemctl status ai-course-engine-backup.service
journalctl -u ai-course-engine-backup.service --since today
```

An untested backup is not a backup. During the first maintenance window, restore
a backup into the stack (or a disposable copy) and verify row counts and
document counts.

### 2.4 Restore

Restore is disruptive: the script stops Caddy, the API, and both workers. Use a
maintenance window.

```bash
sudo bash restore.sh \
  data/backups/postgres-YYYYMMDDTHHMMSSZ.dump \
  data/backups/storage-YYYYMMDDTHHMMSSZ.tar.gz
```

The script:

1. Takes a safety backup unless `SKIP_BACKUP=1`.
2. Stops application services.
3. Verifies the dump can be listed.
4. Terminates other connections to the target database.
5. Restores with `pg_restore --clean --if-exists --no-owner --no-privileges`.
6. Restores uploaded documents and fixes ownership.
7. Runs migrations and starts the stack.

Use `SKIP_BACKUP=1` only when the current database is unusable:

```bash
sudo SKIP_BACKUP=1 bash restore.sh data/backups/postgres-....dump data/backups/storage-....tar.gz
```

After restore:

```bash
bash healthcheck.sh --local
docker compose --env-file .env.production -f compose.yaml ps -a
```

If the application is restored but Caddy cannot obtain a certificate because
DNS is not pointed at the VM, Caddy logs will show ACME failures; the API can
still be checked inside the container.

## 3. Updates

1. Announce a maintenance window if the migration may lock tables.
2. Take a fresh backup and copy it off the VM.
3. Review the incoming changes before pulling.
4. Update without discarding server-side changes:

   ```bash
   cd /opt/ai-course-engine
   git status
   git pull --ff-only
   ```

5. Rebuild only the application image:

   ```bash
   cd deploy/oci
   docker compose --env-file .env.production -f compose.yaml build api
   ```

6. Reconcile services. Compose runs the one-shot migration before the API:

   ```bash
   docker compose --env-file .env.production -f compose.yaml up -d
   ```

7. Watch startup:

   ```bash
   docker compose --env-file .env.production -f compose.yaml ps -a
   docker compose --env-file .env.production -f compose.yaml logs --tail=100 migrate api
   bash healthcheck.sh --local
   ```

8. If the migration fails, do not start the new API repeatedly. Stop the
   application, restore the pre-update database backup, and investigate the
   migration. Do not run `alembic downgrade` against production without an
   approved plan.

To update base images (Postgres, Redis, Caddy), review release notes and take a
backup first:

```bash
docker compose --env-file .env.production -f compose.yaml pull postgres redis caddy
docker compose --env-file .env.production -f compose.yaml up -d
```

Do not use `docker system prune -a --volumes` on this host. It can remove
images or volumes needed for rollback.

## 4. Monitoring

### 4.1 Health checks

Manual:

```bash
bash healthcheck.sh          # includes public HTTPS checks
bash healthcheck.sh --local  # container/internal checks only
```

Scheduled checks every five minutes:

```bash
sudo cp systemd/ai-course-engine-health.service /etc/systemd/system/
sudo cp systemd/ai-course-engine-health.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-course-engine-health.timer
systemctl list-timers ai-course-engine-health.timer
journalctl -u ai-course-engine-health.service --since today
```

The timer only logs failures; it does not send alerts. Add an external uptime
monitor against the public readiness endpoint if alerting is required. Keep the
existing Vercel frontend monitored separately.

### 4.2 Logs

```bash
docker compose --env-file .env.production -f compose.yaml logs -f caddy
docker compose --env-file .env.production -f compose.yaml logs -f api
docker compose --env-file .env.production -f compose.yaml logs -f ingestion-worker
docker compose --env-file .env.production -f compose.yaml logs -f content-worker
```

Caddy writes JSON access logs to stdout. Docker rotates logs at 10 MB × 5.
`journalctl` is used for the systemd backup/health timers:

```bash
journalctl -u ai-course-engine-backup.service --since "7 days ago"
journalctl -u ai-course-engine-health.service --since "1 hour ago"
```

### 4.3 Resource checks

```bash
df -h
du -sh data/*
free -h
docker stats --no-stream
docker system df
```

Watch for:

- Root/boot volume usage above 80%.
- Backup growth beyond local retention.
- PostgreSQL memory pressure near the 12 GB VM limit.
- Worker restarts or repeated failed health checks.
- Caddy certificate renewal failures.

OCI Console compute metrics are useful for CPU, network, and disk. Do not add
paid monitoring or notification services without approval.

## 5. Troubleshooting

### Caddy has no certificate or TLS fails

- Confirm `api.skillupactionafrica.co.ke` resolves to the VM public IPv4.
- Confirm OCI security list and UFW allow inbound 80 and 443.
- Check that no CNAME exists at `api` alongside the A record.
- Check CAA records if the zone has any; they must permit the ACME CA Caddy uses.
- Inspect `docker compose logs caddy` for ACME errors.
- Do not repeatedly restart Caddy while ACME is rate-limited; fix DNS/firewall
  first.

### Browser gets 502

1. Check `api` health with `healthcheck.sh --local`.
2. Check `docker compose ps`.
3. Check `docker compose logs --tail=200 api`.
4. Confirm PostgreSQL and Redis are healthy.
5. Confirm the API is on the `edge` network and Caddy can resolve `api`.

### Migration failed

```bash
docker compose --env-file .env.production -f compose.yaml logs migrate
```

Common causes: `DATABASE_URL` password does not match `POSTGRES_PASSWORD`, the
database container was unhealthy, or a migration conflicts with restored data.
Do not expose the environment file while diagnosing.

### PostgreSQL will not start after data-directory changes

Check ownership:

```bash
sudo ls -ld data/postgres
```

The official `postgres:17-alpine` image uses uid/gid `70:70` in this stack.
Re-run `bootstrap.sh` or correct ownership, then inspect Postgres logs before
retrying.

### Redis will not start

Check ownership:

```bash
sudo ls -ld data/redis
```

The Redis image uses uid/gid `999:1000`. Re-run `bootstrap.sh` or correct
ownership.

### Worker is unhealthy

The health check verifies that PID 1 is still the expected worker module. Check:

```bash
docker compose --env-file .env.production -f compose.yaml logs --tail=200 ingestion-worker
docker compose --env-file .env.production -f compose.yaml logs --tail=200 content-worker
```

If it is crash-looping, fix the underlying database, Redis, AI, or Moodle
configuration. Do not disable the health check as a workaround.

### Disk full

```bash
df -h
du -sh data/backups data/postgres data/storage
docker system df
```

Delete only backups older than the retention policy after confirming offsite
copies. Do not delete the live Postgres or storage directories.

### Out of memory

```bash
free -h
docker stats --no-stream
```

The total VM is 12 GB. Keep the Compose Postgres tuning values under review;
reduce worker concurrency only through supported application settings, not by
editing running containers. Do not resize to a paid shape without approval.

### OCI reports A1 out-of-host-capacity

Try another availability domain or wait and retry. Do not switch to a paid
shape or add extra OCPU/RAM without approval.

### Vercel frontend cannot call the API

- The API base URL is baked into the Vite build. Changing
  `VITE_API_BASE_URL` requires a new Vercel deployment.
- `CORS_ORIGINS` must contain the exact browser origins, including `https://`
  and the apex/`www` distinction.
- Check the network response for a CORS error versus a TLS/502 error.
- Google OAuth failures are separate: the callback URI in Google Cloud must
  exactly match `GOOGLE_OAUTH_REDIRECT_URI`.

### Upload returns 413

Caddy allows up to 55 MB; the application allows up to 50 MB. Raise both only
through an approved configuration change, and consider disk and processing
impact first.

## 6. Emergency stop and recovery

To stop public access without deleting data:

```bash
docker compose --env-file .env.production -f compose.yaml stop caddy
```

To stop application processing while keeping the database:

```bash
docker compose --env-file .env.production -f compose.yaml stop \
  caddy api ingestion-worker content-worker
```

To start again:

```bash
docker compose --env-file .env.production -f compose.yaml up -d
```

Never use `down -v` as part of routine recovery. If the database or storage is
damaged, stop the application, preserve the current files for diagnosis, and
restore from a verified backup.
