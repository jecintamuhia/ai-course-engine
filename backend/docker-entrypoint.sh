#!/bin/sh
set -eu

upload_dir="${UPLOAD_DIR:-/app/storage/documents}"
storage_root="$(dirname "$upload_dir")"

# Container runtimes often attach volumes as root. Prepare the mount (and
# correct its ownership) while privileged, then run the application as appuser.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$upload_dir"
    chown -R appuser:appuser "$storage_root" 2>/dev/null || true
    exec gosu appuser "$@"
fi

mkdir -p "$upload_dir" 2>/dev/null || true
exec "$@"
