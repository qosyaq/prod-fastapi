#!/usr/bin/env bash

set -e

echo "Applying migrations..."
uv run alembic upgrade head
echo "Migrations applied."

exec "$@"