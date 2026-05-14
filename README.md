# prod-fastapi

Personal reference. Covers how to run, how configs work, logging, observability, and why the folder structure is the way it is.

---

## How docker-compose is structured

Services are split into **profiles** — they don't all start by default:

| Service | Profile | Always starts |
|---|---|---|
| `pg` | — | yes |
| `adminer` | — | yes |
| `app-main` | `app` | no |
| `loki`, `prometheus`, `tempo`, `grafana` | `observability` | no |

`pg` and `adminer` start with any `docker compose up`.

---

## Running

### Only DB (local dev)

```bash
docker compose up -d
```

Starts `pg` on port `5432`, `adminer` on `8080`.

Then run the app locally:

```bash
cd backend
uv sync --group dev
# create backend/config/.env with your vars (copy from .env.example as reference)
uv run python src/run_main.py
```

### App in Docker (staging)

The `app-main` service reads `env_file: .env.${ENV:-example}`. Pass `ENV` to select which file to load from the project root:

```bash
ENV=staging docker compose --profile app up -d
```

This loads `.env.staging` and passes all vars to the container. To rebuild the image:

```bash
ENV=staging docker compose --profile app up -d --build
```

### Full stack with observability

```bash
ENV=staging docker compose --profile app --profile observability up -d
```

- App: `http://localhost:8000`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Adminer: `http://localhost:8080`

### Useful commands

```bash
# Logs
docker compose logs -f app-main

# Open psql
docker compose exec pg psql -U user -d app

# Rebuild only app
ENV=staging docker compose --profile app up -d --build app-main
```

---

## How configuration works

### Pattern: Pydantic BaseSettings + nested `__` delimiter

All settings in `backend/src/config.py`. One root `Settings` class with nested models:

```
Settings
├── env                          # "development" | "staging" | "production"
├── title, debug, description, version
├── run: RunConfig               # host, port, workers, timeout
├── logging: LogConfig           # level, fmt
├── observability: ObsConfig     # app_name, otlp_grpc_endpoint
└── postgres: PostgresConfig     # host, port, user, password, db, pool settings
```

### Env var naming

Prefix `API__`, nested levels separated by `__`:

```bash
API__ENV=staging
API__RUN__WORKERS=4
API__LOGGING__LEVEL=DEBUG
API__POSTGRES__HOST=pg
API__POSTGRES__ECHO=true        # logs every SQL query
API__POSTGRES__ECHO_POOL=true   # logs pool events
```

### Where config files are loaded from

`config.py` defines:
```python
env_file=["config/.env", "config/.env.development"]
```

This path is **relative to the working directory** (`backend/`). In Docker, no `.env` files are copied into the image — config comes entirely from environment variables passed via `env_file` in docker-compose. Locally, create `backend/config/.env` manually (use `.env.example` at the project root as a reference for what keys exist).

Priority (highest wins): environment variables → `config/.env.development` → `config/.env` → defaults in code.

### Why Pydantic Settings

Validation at startup — a typo in an env var crashes immediately with a clear error instead of silently using a wrong value at runtime. Nested models keep related config grouped.

---

## How logging works

Setup in `backend/src/logger.py` — called once at startup from `main.py`:

```python
def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=settings.logging.fmt))
    logging.basicConfig(level=settings.logging.level, handlers=[handler])
```

Single `StreamHandler` → stdout. Container infra (Docker, Loki driver) handles the rest.

### Log format

```
2026-05-14 12:00:00 INFO [tasks.service] [service.py:42]
[trace_id=abc123 span_id=def456 resource.service.name=app-main] - Created task id=1
```

`trace_id` and `span_id` are injected automatically by `LoggingInstrumentor` from OpenTelemetry. Every log line is correlated to a trace — this is what makes Grafana's logs→traces drill-down work.

### Access log filtering

`/metrics` is scraped by Prometheus every 5s — would spam access logs. Filtered out in `main.py`:

```python
class EndpointFilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().find("GET /metrics") == -1

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
```

### Gunicorn log integration

`backend/src/master/logger.py` has a custom `GunicornLogger` that reuses the same formatter as the app — so gunicorn access logs and app logs look identical.

### Log levels

- `INFO` — default, production-safe
- `DEBUG` — set `API__LOGGING__LEVEL=DEBUG` + `API__POSTGRES__ECHO=true` for full SQL query logging

---

## How the app starts

### Entry point

```
entrypoint.sh
  → clean stale Prometheus multiprocess files
  → uv run alembic upgrade head
  → uv run python src/run_main.py
        → Application(app, options).run()   # gunicorn BaseApplication
             → gunicorn forks N workers
                  → each worker runs uvicorn (UvicornWorker)
                       → serves FastAPI app
```

### Gunicorn wrapper (`backend/src/master/`)

`master/` is a thin wrapper around gunicorn's `BaseApplication`. It exists so `main.py` stays clean (just FastAPI app definition) and the launch logic is separate. Three files:

- `application.py` — `Application(BaseApplication)`: takes FastAPI app + options dict, passes to gunicorn
- `app_options.py` — `get_app_options()`: builds the options dict from settings; also has `_child_exit` hook to clean up Prometheus multiprocess files when a worker exits
- `logger.py` — `GunicornLogger`: gunicorn's logger subclass, uses the same format as the app

### Why gunicorn + UvicornWorker

Gunicorn handles worker management (process lifecycle, graceful restarts, SIGTERM handling). Uvicorn handles the actual async serving. Together: production-grade process management + async FastAPI support.

---

## Observability stack

```
App → Prometheus  (metrics, scraped every 5s)
App → Tempo       (traces via OTLP gRPC)
App → Loki        (logs via Docker loki logging driver)
All → Grafana     (dashboards, exemplar correlation between all three)
```

### Metrics (Prometheus)

`PrometheusMiddleware` in `observability_utils.py` instruments every request:

- `fastapi_requests_total` — counter, labels: method, path, app_name
- `fastapi_responses_total` — counter, labels: method, path, status_code, app_name
- `fastapi_requests_duration_seconds` — histogram (includes TraceID as exemplar)
- `fastapi_requests_in_progress` — gauge
- `fastapi_exceptions_total` — counter by exception type

Endpoint: `GET /metrics`.

Multiple gunicorn workers → Prometheus multiprocess mode. Each worker writes metrics to files in `$PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc`. `entrypoint.sh` cleans this dir on startup to avoid stale data from previous runs. `_child_exit` in `app_options.py` marks a worker's files as dead when it exits.

### Traces (Tempo)

`setting_otlp()` in `observability_utils.py` sets up:
- `FastAPIInstrumentor` — span per HTTP request
- `SQLAlchemyInstrumentor` — child spans for every DB query
- `LoggingInstrumentor` — injects trace_id/span_id into log records

Spans are exported to Tempo via gRPC at `API__OBSERVABILITY__OTLP_GRPC_ENDPOINT` (default: `localhost:4317`, staging: `tempo:4317`).

The histogram records TraceID as an exemplar — in Grafana you can click a latency spike and jump directly to the specific trace.

### Logs (Loki)

Docker Compose uses `driver: loki` for app/prometheus/tempo/grafana containers. Loki parses the timestamp from log lines via regex. Grafana's Loki datasource has a derived field that extracts `trace_id` from log text and links to Tempo.

### Grafana

Three datasources provisioned automatically from `observability/grafana/datasource.yml`:

| Datasource | Internal URL |
|---|---|
| Prometheus (default) | `prometheus:9090` |
| Tempo | `tempo:3200` |
| Loki | `loki:3100` |

Dashboard loaded from `observability/dashboards/fastapi-observability.json`.

**Drill-down flow:** metric spike → click exemplar → Tempo trace → click `trace_id` field → Loki logs for that exact request.

---

## Database & migrations

### SQLAlchemy async

`backend/src/db/session.py` — async engine via `asyncpg`. Pool defaults: 50 connections, 10 overflow.

### Base model with naming convention

`backend/src/db/base.py` — `DeclarativeBase` with explicit `naming_convention`. Ensures Alembic generates deterministic constraint names (e.g. `fk_tasks_user_id_users`) instead of Postgres auto-names. Matters when you need to drop/rename constraints in future migrations.

### Mixins (`backend/src/db/mixins.py`)

```python
class IdIntPkMixin:    # id: int primary key
class TimestampMixin:  # created_at, updated_at with server-side defaults
```

Usage: `class TaskOrm(IdIntPkMixin, TimestampMixin, Base)`.

### Alembic

Config in `backend/alembic.ini`. Migration files named by date:
```
2026_05_04_2120-ca6d219b0627_create_tasks_table.py
```

Common commands (run from `backend/`):

```bash
# Generate migration from model changes
uv run alembic revision --autogenerate -m "add_users_table"

# Apply all pending
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1

# Check current revision
uv run alembic current
```

Migrations run automatically on container start via `entrypoint.sh`.

---

## Folder architecture

```
prod-fastapi/
├── backend/
│   ├── src/                        # All Python source (PYTHONPATH=/app/src in Docker)
│   │   ├── main.py                 # FastAPI app + lifespan hooks
│   │   ├── run_main.py             # Entry point: builds gunicorn options, calls .run()
│   │   ├── config.py               # All settings (one import: from config import settings)
│   │   ├── logger.py               # configure_logging(), called once at startup
│   │   ├── router.py               # Mounts domain routers under /api/v1
│   │   ├── exceptions.py           # Global exception handlers
│   │   ├── observability_utils.py  # PrometheusMiddleware + OpenTelemetry init
│   │   ├── db/                     # Engine, sessionmaker, DeclarativeBase, mixins
│   │   ├── master/                 # Gunicorn Application wrapper + options + logger
│   │   └── tasks/                  # Domain module
│   ├── migrations/                 # Alembic (separate from src)
│   ├── scripts/entrypoint.sh
│   └── tests/
├── observability/                  # Prometheus, Tempo, Loki, Grafana configs
└── docker-compose.yml
```

### Why `src/` layout

Without `src/`, Python adds the project root to `sys.path` and you risk accidentally importing a local file instead of an installed package (name collision). With `src/`:

- Docker sets `PYTHONPATH=/app/src` → `from config import settings` works everywhere
- `pyproject.toml` sets `pythonpath = ["src"]` → same for tests
- No path manipulation, no `sys.path` hacks

### Why domain modules

Each domain has a fixed structure: `router.py`, `service.py`, `models.py`, `schemas.py`, `dependencies.py`, `exceptions.py`, `constants.py`. Adding a new domain (e.g. `users/`) means replicating this structure. You always know where things live without reading the code. Router only does HTTP, service only does business logic.

### Why `master/` is separate

Gunicorn is infrastructure, not application code. Keeping the launch logic in `master/` means `main.py` is pure FastAPI (app definition, middleware, routes) and `run_main.py` is just the entry point. Swapping gunicorn for something else → touch only `master/` and `run_main.py`.

---

## Dev cheatsheet

```bash
cd backend

# Install all deps including dev
uv sync --group dev

# Format
uv run black .

# Lint (with autofix)
uv run ruff check . --fix

# Tests
uv run pytest
uv run pytest -v tests/tasks/

# Run locally
uv run python src/run_main.py

# New migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```
