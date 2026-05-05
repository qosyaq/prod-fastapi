#!/usr/bin/env bash

set -e

# Clean stale prometheus metric files from previous run
if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
    rm -rf "$PROMETHEUS_MULTIPROC_DIR"
    mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

echo "Applying migrations..."
uv run alembic upgrade head
echo "Migrations applied."

exec "$@"