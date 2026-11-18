#!/usr/bin/env bash
#
# One-time Ubuntu LTS ARM64 host preparation for the OCI Always Free backend.
# Run as root from a cloned repository:
#
#   sudo bash deploy/oci/bootstrap.sh
#
# This script installs Docker, enables a deny-by-default host firewall, and
# creates persistent data directories. It does not start the application and
# does not contain production secrets.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root: sudo bash deploy/oci/bootstrap.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
TARGET_USER="${SUDO_USER:-ubuntu}"

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  chrony \
  curl \
  fail2ban \
  gnupg \
  logrotate \
  ufw

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable
EOF

apt-get update
apt-get install -y --no-install-recommends \
  containerd.io \
  docker-buildx-plugin \
  docker-ce \
  docker-ce-cli \
  docker-compose-plugin

systemctl enable --now chrony
timedatectl set-timezone UTC
systemctl enable --now docker

if id "${TARGET_USER}" >/dev/null 2>&1; then
  usermod -aG docker "${TARGET_USER}"
fi

# Keep container logs bounded. Preserve any existing daemon configuration.
mkdir -p /etc/docker
if [[ -f /etc/docker/daemon.json ]]; then
  cp /etc/docker/daemon.json "/etc/docker/daemon.json.bak.$(date -u +%Y%m%dT%H%M%SZ)"
fi
cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}
JSON
systemctl restart docker

# Host firewall. Docker-published ports bypass UFW, so the Compose file is
# deliberately the only thing allowed to publish ports (Caddy 80/443).
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat > /etc/fail2ban/jail.d/sshd.local <<'JAIL'
[sshd]
enabled = true
JAIL
systemctl enable --now fail2ban

cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT
systemctl enable --now unattended-upgrades

# Persistent data. These UIDs match the official images used by Compose.
install -d -m 0700 -o 70 -g 70 "${DATA_DIR}/postgres"
install -d -m 0700 -o 999 -g 1000 "${DATA_DIR}/redis"
install -d -m 0750 -o 1000 -g 1000 "${DATA_DIR}/storage"
install -d -m 0750 -o 1000 -g 1000 "${DATA_DIR}/storage/documents"
install -d -m 0700 -o 0 -g 0 "${DATA_DIR}/caddy/data"
install -d -m 0700 -o 0 -g 0 "${DATA_DIR}/caddy/config"
install -d -m 0700 -o 0 -g 0 "${DATA_DIR}/backups"

cat <<EOF

Bootstrap complete.

Next steps:
1. Log out and back in so ${TARGET_USER} receives Docker group membership.
2. Copy the repository to /opt/ai-course-engine if it is not already there.
3. cd ${SCRIPT_DIR}
4. cp .env.production.example .env.production
5. Fill every CHANGE_ME value, then: chmod 600 .env.production
6. Validate: python3 validate_env.py
7. Test: docker compose --env-file .env.production -f compose.yaml config >/dev/null
8. Deploy: docker compose --env-file .env.production -f compose.yaml up -d --build

Do not change DNS, issue a production certificate, or enable Google OAuth
until the owner has approved those actions.

Do not open Postgres (5432), Redis (6379), or the API (8000) in the OCI
security list or NSG. Only 22, 80, and 443 should be reachable.
EOF
