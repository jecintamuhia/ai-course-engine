#!/usr/bin/env bash
#
# Consistent PostgreSQL + uploaded-document backup.
#
#   sudo bash deploy/oci/backup.sh
#
# Backups are written to deploy/oci/data/backups and retained for
# BACKUP_RETENTION_DAYS (default 14). Copy them off the VM regularly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.production"
COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
BACKUP_DIR="${SCRIPT_DIR}/data/backups"
STORAGE_DIR="${SCRIPT_DIR}/data/storage"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

RETENTION_DAYS="$(
  awk -F= '$1 == "BACKUP_RETENTION_DAYS" { print $2; exit }' "${ENV_FILE}" \
    | tr -d '\r'
)"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if ! [[ "${RETENTION_DAYS}" =~ ^[0-9]+$ ]] || (( RETENTION_DAYS < 1 )); then
  echo "BACKUP_RETENTION_DAYS must be a positive integer" >&2
  exit 1
fi

COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

"${COMPOSE[@]}" exec -T postgres sh -lc \
  'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null

install -d -m 0700 "${BACKUP_DIR}"
umask 077

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="${BACKUP_DIR}/postgres-${STAMP}.dump"
TMP_DUMP="${DUMP}.tmp"
ARCHIVE="${BACKUP_DIR}/storage-${STAMP}.tar.gz"
TMP_ARCHIVE="${ARCHIVE}.tmp"

echo "Backing up PostgreSQL to ${DUMP}"
"${COMPOSE[@]}" exec -T postgres sh -lc \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${TMP_DUMP}"

"${COMPOSE[@]}" exec -T postgres pg_restore --list < "${TMP_DUMP}" >/dev/null
mv "${TMP_DUMP}" "${DUMP}"

echo "Backing up uploaded documents to ${ARCHIVE}"
tar -C "${STORAGE_DIR}" -czf "${TMP_ARCHIVE}" .
tar -tzf "${TMP_ARCHIVE}" >/dev/null
mv "${TMP_ARCHIVE}" "${ARCHIVE}"

(
  cd "${BACKUP_DIR}"
  sha256sum "$(basename "${DUMP}")" "$(basename "${ARCHIVE}")" \
    > "SHA256SUMS-${STAMP}.txt"
)

find "${BACKUP_DIR}" -type f -mtime "+${RETENTION_DAYS}" -delete

echo "Backup complete:"
ls -lh "${DUMP}" "${ARCHIVE}" "${BACKUP_DIR}/SHA256SUMS-${STAMP}.txt"
