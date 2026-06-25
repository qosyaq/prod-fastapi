FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --no-group dev --no-install-project

COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY src ./src
COPY scripts ./scripts

RUN uv sync --no-group dev
RUN chmod +x scripts/entrypoint.sh

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["uv", "run", "python", "src/run_main.py"]
