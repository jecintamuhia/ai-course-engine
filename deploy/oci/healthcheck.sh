#!/usr/bin/env bash
#
# Read-only health check for the OCI stack.
#
#   bash deploy/oci/healthcheck.sh          # includes public HTTPS checks
#   bash deploy/oci/healthcheck.sh --local  # skips public DNS/TLS checks
#
# Exit status is non-zero if any check fails.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.production"
COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
MODE="${1:-public}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

DOMAIN="$(
  awk -F= '$1 == "CADDY_DOMAIN" { print $2; exit }' "${ENV_FILE}" \
    | tr -d '\r'
)"
if [[ -z "${DOMAIN}" ]]; then
  echo "CADDY_DOMAIN is missing from ${ENV_FILE}" >&2
  exit 1
fi

COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

echo "Container status:"
"${COMPOSE[@]}" ps

echo "PostgreSQL readiness:"
"${COMPOSE[@]}" exec -T postgres sh -lc \
  'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

echo "Redis readiness:"
"${COMPOSE[@]}" exec -T redis redis-cli ping

echo "API readiness (inside the API container):"
"${COMPOSE[@]}" exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=10)"

echo "API liveness (inside the API container):"
"${COMPOSE[@]}" exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=10)"

if [[ "${MODE}" == "--local" ]]; then
  echo "Skipping public HTTPS checks (--local)."
  exit 0
fi

echo "Public readiness: https://${DOMAIN}/health/ready"
curl -fsS --max-time 20 "https://${DOMAIN}/health/ready"
echo

echo "Public liveness: https://${DOMAIN}/api/v1/health"
curl -fsS --max-time 20 "https://${DOMAIN}/api/v1/health"
echo

echo "All checks passed."
