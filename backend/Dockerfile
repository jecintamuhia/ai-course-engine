FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System dependencies required for PostgreSQL client compilation/runtime
# and gosu, which lets the entrypoint prepare a mounted storage volume before
# dropping privileges to the unprivileged application user.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements ./requirements

RUN pip install --upgrade pip \
    && pip install -r requirements/production.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh /app/scripts/*.sh \
    && useradd \
        --create-home \
        --shell /usr/sbin/nologin \
        appuser \
    && mkdir -p /app/storage/documents \
    && chown -R appuser:appuser /app

# The entrypoint starts as root only long enough to create/chown the
# mounted storage path, then drops to appuser. Container runtimes often mount
# volumes as root, so this is required for a persistent upload directory.
ENV UPLOAD_DIR=/app/storage/documents

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
