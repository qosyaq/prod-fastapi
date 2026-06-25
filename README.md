# prod-fastapi

Production-ready FastAPI monolith template. Personal reference for config, logging, observability, and project structure.

---

## Running

### Local dev

```bash
cd backend
uv sync --group dev
# create backend/config/.env (see .env.example for reference)
uv run python src/run_main.py
```

Postgres and other infra can be started separately:

```bash
docker compose up pg adminer -d
```

### Full stack in Docker

```bash
ENV=staging docker compose up -d
ENV=staging docker compose up -d --build   # rebuild app image
```

`app-a` reads `env_file: .env.${ENV:-example}` from project root. All services start together.

| Service    | URL                     |
|------------|-------------------------|
| App        | http://localhost:8000   |
| Grafana    | http://localhost:3000   |
| Prometheus | http://localhost:9090   |
| Adminer    | http://localhost:8080   |

---

## How the app starts

```
entrypoint.sh
  → clean $PROMETHEUS_MULTIPROC_DIR
  → uv run alembic upgrade head
  → uv run python src/run_main.py
        → gunicorn with UvicornWorker
             → N workers, each runs FastAPI app
                  → lifespan: log start → serve → dispose engine on shutdown
```

Gunicorn config lives in `gunicorn_app.py`: worker class, timeout, logger, and a `_child_exit` hook that marks a dead worker's Prometheus files as inactive.

---

## Configuration

All settings in `src/config.py`. One root `Settings` with nested models:

```
Settings                          prefix: API__
├── env                           API__ENV=staging
├── title, debug, version         API__DEBUG=true
├── run: RunConfig
│   ├── host                      API__RUN__HOST=0.0.0.0
│   ├── port                      API__RUN__PORT=8000
│   ├── workers                   API__RUN__WORKERS=4
│   └── timeout                   API__RUN__TIMEOUT=30
├── logging: LogConfig
│   ├── level                     API__LOGGING__LEVEL=DEBUG
│   ├── fmt                       # plain format (dev)
│   └── fmt_otlp                  # format with trace_id/span_id (staging+)
├── observability: ObservabilityConfig | None
│   ├── app_name                  API__OBSERVABILITY__APP_NAME=app-a
│   └── otlp_grpc_endpoint        API__OBSERVABILITY__OTLP_GRPC_ENDPOINT=tempo:4317
└── postgres: PostgresConfig
    ├── host, port, user, password, db
    ├── echo                      API__POSTGRES__ECHO=true    # log all SQL
    ├── echo_pool                 API__POSTGRES__ECHO_POOL=true
    ├── pool_size                 # 15 (default)
    └── max_overflow              # 5  (default)
```

**Priority:** env vars → `config/.env.development` → `config/.env` → code defaults.

In Docker, no `.env` files are copied — config comes entirely from `env_file` in docker-compose.

`settings.observability_enabled` is `True` when `env != development` and `observability` is set. Controls whether OTel and Prometheus are activated.

---

## Logging

Configured once at startup by `configure_logging()` in `logger.py`.

**Dev format:**
```
[2026-05-14 12:00:00,123]          tasks.service:42  INFO     - Task created
```

**Staging/prod format (OTel injected):**
```
2026-05-14 12:00:00 INFO [src.tasks.service] [service.py:42] [trace_id=abc span_id=def resource.service.name=app-a] - Task created
```

`trace_id` and `span_id` are injected automatically by `LoggingInstrumentor`. Every log line is correlated to a trace — this is what enables Grafana's Loki → Tempo drill-down.

`GET /metrics` access logs are suppressed (Prometheus scrapes it every 5s).

---

## Observability

```
App → /metrics endpoint     → Prometheus (scraped every 5s)
App → OTLP gRPC (4317)      → Tempo (traces)
App → stdout                → Docker Loki driver → Loki (logs)
All → Grafana               (dashboards + correlation)
```

Everything is set up in one call from `main.py`:

```python
if settings.observability_enabled:
    setup_observability(app)
```

**Metrics** — `PrometheusMiddleware` tracks per-request:

| Metric | Type |
|--------|------|
| `fastapi_requests_total` | Counter |
| `fastapi_responses_total` | Counter |
| `fastapi_requests_duration_seconds` | Histogram |
| `fastapi_requests_in_progress` | Gauge |
| `fastapi_exceptions_total` | Counter |

The histogram includes a `TraceID` exemplar on each observation — clicking a spike in Grafana jumps directly to that trace in Tempo.

Multiple gunicorn workers → Prometheus multiprocess mode via `$PROMETHEUS_MULTIPROC_DIR`.

**Traces** — three instrumentors:

- `FastAPIInstrumentor` — one span per HTTP request
- `SQLAlchemyInstrumentor` — child spans per SQL query (engine passed explicitly so spans are captured correctly)
- `LoggingInstrumentor` — injects `trace_id`/`span_id` into every log record

**Drill-down flow:** Grafana metric spike → click exemplar → Tempo trace (full span tree with SQL queries) → click `trace_id` → Loki logs for that exact request.

Grafana datasources and dashboards are provisioned automatically from `observability/grafana/` and `observability/dashboards/`.

---

## Database

**Engine** (`db/session.py`): async via `asyncpg`, pool size 15 + 5 overflow.

**Base** (`db/base.py`): `DeclarativeBase` with explicit `naming_convention` — constraint names like `fk_tasks_user_id_users` instead of Postgres auto-names. Matters when dropping/renaming constraints in migrations.

**Mixins** (`db/mixins.py`):

```python
class IdIntPkMixin:    # id: int primary key
class TimestampMixin:  # created_at, updated_at (server-side defaults)
```

**Migrations:** Alembic with async engine. File naming: `YYYY_MM_DD_HHMM-<rev>_<slug>.py`. Post-write hook runs `ruff` on each new file. Migrations run automatically on container start via `entrypoint.sh`.

```bash
# from backend/
uv run alembic revision --autogenerate -m "add_users_table"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic current
```

---

## Domain modules

Each domain follows a fixed structure — you always know where things live:

```
tasks/
├── constants.py     # TaskStatus enum
├── models.py        # TaskOrm (SQLAlchemy)
├── schemas.py       # TaskCreate, TaskUpdate, TaskResponse (Pydantic)
├── service.py       # Business logic (async, takes AsyncSession)
├── router.py        # FastAPI APIRouter — HTTP only, calls service
├── dependencies.py  # get_task_or_404 shared dependency
└── exceptions.py    # TaskNotFound HTTPException
```

Adding a new domain means replicating this structure under `src/<domain>/`.

---

## Testing

Tests use transactional isolation: each test runs in a transaction that is rolled back after the test — no cleanup needed, no shared state.

```python
# conftest.py — key idea
async with engine.connect() as conn:
    await conn.begin()
    async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as sess:
        yield sess
    await conn.rollback()   # ← always rolled back
```

`client` fixture overrides `session_getter` to use the test session, so HTTP tests hit the same transaction.

```bash
uv run pytest
uv run pytest -v tests/tasks/
```

---

## Folder structure

```
prod-fastapi/
├── backend/
│   ├── src/
│   │   ├── main.py            # FastAPI app, lifespan, middleware
│   │   ├── run_main.py        # Entry point → gunicorn
│   │   ├── config.py          # All settings (one import: from src.config import settings)
│   │   ├── logger.py          # configure_logging()
│   │   ├── gunicorn_app.py    # GunicornLogger + get_app_options()
│   │   ├── observability.py   # PrometheusMiddleware + setup_observability()
│   │   ├── router.py          # Mounts domain routers under /api/v1
│   │   ├── exceptions.py      # Global exception handlers
│   │   ├── constants.py       # Environment enum
│   │   ├── db/                # Engine, session, Base, mixins
│   │   └── tasks/             # Domain module
│   ├── migrations/            # Alembic (env.py + versions/)
│   ├── scripts/entrypoint.sh
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── observability/
│   ├── prometheus/prometheus.yml
│   ├── tempo/tempo.yml
│   ├── grafana/datasource.yml
│   └── dashboards/
└── docker-compose.yml
```

`src/` layout prevents name collisions with installed packages. `PYTHONPATH=/app` in Docker, `pythonpath = ["."]` in pytest config.

---

## Dev cheatsheet

```bash
cd backend

uv sync --group dev
uv run python src/run_main.py

uv run black .
uv run ruff check . --fix
uv run pytest

uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

docker compose logs -f app-a
docker compose exec pg psql -U user -d app
```