# OCI Always Free deployment

This directory is the production target for the SkillUp Action Africa backend.
It replaces Railway with one Always Free ARM64 VM running Docker Compose.

Read `docs/oci-deployment.md` before changing DNS. Never commit
`.env.production` or anything under `data/`.

## Files

| File | Purpose |
| --- | --- |
| `compose.yaml` | Caddy, API, PostgreSQL, Redis, ingestion worker, content worker |
| `Caddyfile` | Automatic TLS, HSTS/security headers, JSON access logs, upload limit |
| `.env.production.example` | Environment template; copy to `.env.production` |
| `bootstrap.sh` | One-time Ubuntu host setup: Docker, UFW, fail2ban, data directories |
| `backup.sh` | PostgreSQL custom-format dump plus uploaded-document archive |
| `restore.sh` | Restore a dump/archive pair, migrate, and restart |
| `healthcheck.sh` | Container, PostgreSQL, Redis, and API checks |
| `validate_env.py` | Rejects placeholders, unsafe secrets, wrong domains, and incomplete OAuth/Moodle config |
| `systemd/` | Daily backup and five-minute health-check timers |

## Minimal runbook

```bash
sudo bash deploy/oci/bootstrap.sh
cd /opt/ai-course-engine/deploy/oci
cp .env.production.example .env.production
chmod 600 .env.production
# edit every CHANGE_ME value
python3 validate_env.py
docker compose --env-file .env.production -f compose.yaml config >/dev/null
docker compose --env-file .env.production -f compose.yaml up -d --build
bash healthcheck.sh --local
```

Only ports 22, 80, and 443 are reachable from outside. PostgreSQL, Redis, and
the API are private Compose services.

Disposable local validation has covered the full Compose stack and a
database/storage backup-restore round trip. The Linux-only `backup.sh` and
`restore.sh` wrappers still need to be run on the target VM before cutover.

Do not apply DNS changes, issue a production TLS certificate, or enable Google
OAuth until the owner has approved each action. See
`docs/production-readiness.md` for the current gate list.
