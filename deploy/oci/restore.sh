#!/usr/bin/env bash
#
# Restore PostgreSQL and uploaded documents from a backup pair.
#
#   sudo bash deploy/oci/restore.sh \
#     data/backups/postgres-YYYYMMDDTHHMMSSZ.dump \
#     data/backups/storage-YYYYMMDDTHHMMSSZ.tar.gz
#
# The application is stopped during the restore. A pre-restore backup is taken
# unless SKIP_BACKUP=1 is set (useful when the current database is unusable).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.production"
COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
STORAGE_DIR="${SCRIPT_DIR}/data/storage"
DUMP="${1:-}"
ARCHIVE="${2:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root: sudo bash deploy/oci/restore.sh ..." >&2
  exit 1
fi

if [[ -z "${DUMP}" || -z "${ARCHIVE}" ]]; then
  echo "Usage: sudo bash deploy/oci/restore.sh <postgres.dump> <storage.tar.gz>" >&2
  exit 1
fi

if [[ ! -f "${DUMP}" || ! -f "${ARCHIVE}" ]]; then
  echo "Backup file not found: ${DUMP} or ${ARCHIVE}" >&2
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

if [[ "${SKIP_BACKUP:-0}" != "1" ]]; then
  echo "Taking a safety backup of the current state..."
  bash "${SCRIPT_DIR}/backup.sh"
fi

echo "Stopping application services..."
"${COMPOSE[@]}" stop caddy api ingestion-worker content-worker || true

echo "Verifying PostgreSQL archive..."
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "${DUMP}" >/dev/null

echo "Restoring PostgreSQL..."
"${COMPOSE[@]}" exec -T postgres sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();"' \
  >/dev/null

"${COMPOSE[@]}" exec -T postgres sh -lc \
  'pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "${DUMP}"

echo "Restoring uploaded documents..."
find "${STORAGE_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
tar -C "${STORAGE_DIR}" -xzf "${ARCHIVE}"
chown -R 1000:1000 "${STORAGE_DIR}"

echo "Applying migrations and starting services..."
"${COMPOSE[@]}" run --rm migrate
"${COMPOSE[@]}" up -d postgres redis api ingestion-worker content-worker caddy

echo "Restore complete. Run: bash ${SCRIPT_DIR}/healthcheck.sh"
