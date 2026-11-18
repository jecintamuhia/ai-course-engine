#!/bin/sh
set -eu

# In the Railway fallback layout volumes cannot be shared between services,
# and the ingestion worker must read the PDFs the API writes. Run the ingestion
# worker alongside the API so both processes see the same /app/storage volume.
# The content worker runs as a separate service because it only needs the
# database. The OCI Compose stack runs each worker as its own service.
if [ "${RUN_INGESTION_WORKER:-true}" = "true" ]; then
    (
        while true; do
            python -m app.workers.ingestion_worker
            status=$?
            echo "ingestion worker exited status=$status; restarting in 5s" >&2
            sleep 5
        done
    ) &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
