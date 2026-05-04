# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IDE & Python Path

**PyCharm**: `src/` is marked as **Source Root**. This means all imports inside `src/` are written without the `src.` prefix — e.g., `from config import settings`, not `from src.config import settings`. Within the same domain module, use relative imports: `from .models import TaskOrm`.

This convention is enforced in three places:
- **alembic.ini**: `prepend_sys_path = ./src`
- **Dockerfile**: `ENV PYTHONPATH=/app/src`
- **pytest** (pyproject.toml): `pythonpath = ["src"]`

## Package Manager

Always use `uv`. Never use `pip` directly.

```bash
uv add <package>            # add runtime dependency
uv add --group dev <pkg>    # add dev dependency
uv sync                     # install all deps
uv run <command>            # run inside venv
```

## Common Commands

```bash
# Lint / format
uv run black src/ tests/

# Tests
uv run pytest                          # all
uv run pytest tests/tasks/             # module
uv run pytest tests/tasks/test_x.py   # file
uv run pytest -k "test_create"        # by name

# Migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1

# Dev server
PYTHONPATH=src uv run uvicorn main:app --reload

# Production entry point
uv run python src/run_main.py
```

## Environments

Three environments: **development** (default), **staging**, **production**.

- `env` field in `Settings` defaults to `"development"`.
- Each environment has its own `.env` file under `config/` and a dedicated `docker-compose.<env>.yml`.
- The app service always uses `env_file: - config/.env.<env>` — never inline `environment:`.
- Locally pydantic-settings reads from `config/.env` and `config/.env.development`.
- The app boots via `scripts/entrypoint.sh`, which runs `alembic upgrade head` then starts gunicorn.

Production/staging launch stack: **gunicorn → uvicorn workers → FastAPI app**.

### Gunicorn / Uvicorn Setup

The gunicorn runner lives in `src/master/` and consists of three files:

**`src/master/application.py`** — custom `BaseApplication` subclass:

```python
from fastapi import FastAPI
from gunicorn.app.base import BaseApplication


class Application(BaseApplication):
    def __init__(self, application: FastAPI, options: dict | None = None) -> None:
        self.options = options or {}
        self.application = application
        super().__init__()

    def load(self) -> FastAPI:
        return self.application

    def load_config(self) -> None:
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)
```

**`src/master/app_options.py`** — builds the options dict; `worker_class` is always `uvicorn.workers.UvicornWorker`:

```python
from .logger import GunicornLogger


def get_app_options(host: str, port: int, timeout: int, workers: int, log_level: str) -> dict:
    return {
        "bind": f"{host}:{port}",
        "workers": workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
        "loglevel": log_level,
        "accesslog": "-",
        "errorlog": "-",
        "logger_class": GunicornLogger,
    }
```

**`src/master/logger.py`** — custom logger applying the app log format:

```python
from logging import Formatter
from gunicorn.glogging import Logger
from config import settings


class GunicornLogger(Logger):
    def setup(self, cfg) -> None:
        super().setup(cfg)
        fmt = Formatter(fmt=settings.logging.fmt, datefmt=settings.logging.datefmt)
        self._set_handler(self.access_log, cfg.accesslog, fmt)
        self._set_handler(self.error_log, cfg.errorlog, fmt)
```

**`src/run_main.py`** — entry point called by `CMD` in Dockerfile:

```python
from config import settings
from master import Application, get_app_options
from main import app


def main() -> None:
    Application(
        application=app,
        options=get_app_options(
            host=settings.run.host,
            port=settings.run.port,
            timeout=settings.run.timeout,
            workers=settings.run.workers,
            log_level=settings.logging.level,
        ),
    ).run()


if __name__ == "__main__":
    main()
```

**`scripts/entrypoint.sh`:**
```bash
#!/usr/bin/env bash
set -e
echo "Applying migrations..."
uv run alembic upgrade head
echo "Migrations applied."
exec "$@"
```

**Dockerfile pattern:**
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

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
```

### Docker Compose Services

Standard services in every `docker-compose.<env>.yml`:

```yaml
services:
  pg:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: change_me
      POSTGRES_DB: app_db
    ports:
      - "5432:5432"
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d app_db"]
      interval: 15s
      timeout: 15s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: >
      redis-server --bind 0.0.0.0 --port 6379 --requirepass change_me
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 15s
      timeout: 15s
      retries: 5

  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      pg:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## Architecture

### Module Layout

Global files live directly in `src/`. Each domain lives in `src/<module>/`:

```
src/
├── config.py          # Global Settings singleton
├── logger.py          # configure_logging()
├── exceptions.py      # register_exception_handlers()
├── router.py          # Central APIRouter (prefix /api/v1)
├── main.py            # FastAPI app factory + lifespan
├── run_main.py        # Gunicorn entry point
├── db/                # Database package
│   ├── __init__.py    # Re-exports: Base, mixins, session_getter, dispose
│   ├── base.py        # DeclarativeBase subclass with MetaData naming convention
│   ├── session.py     # async engine, session_factory, session_getter, dispose
│   └── mixins.py      # IdIntPkMixin, TimestampMixin
├── master/            # Gunicorn runner package
│   ├── __init__.py    # Re-exports: Application, get_app_options
│   ├── application.py
│   ├── app_options.py
│   └── logger.py
└── <module>/
    ├── __init__.py    # Re-exports the router as <module>_router
    ├── router.py
    ├── schemas.py
    ├── models.py
    ├── dependencies.py
    ├── service.py
    ├── constants.py
    └── exceptions.py
```

### Import Conventions

Cross-module imports use no prefix (source root = `src/`):
```python
from config import settings
from db import Base, session_getter, dispose
from tasks import tasks_router
```

Within-module imports use relative:
```python
from .models import TaskOrm
from .exceptions import TaskNotFound
```

### Domain Module `__init__.py`

Every domain module exports its router so `src/router.py` can import it cleanly:

```python
# src/tasks/__init__.py
__all__ = ["tasks_router"]
from .router import router as tasks_router
```

```python
# src/router.py
from fastapi import APIRouter
from tasks import tasks_router

router = APIRouter(prefix="/api/v1")
router.include_router(tasks_router)
```

### `db/` Package

`src/db/base.py` — `DeclarativeBase` subclass with naming conventions from `PostgresConfig`:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from config import settings

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=settings.postgres.naming_convention)
```

`src/db/__init__.py` re-exports everything so domain models only need `from db import Base, IdIntPkMixin, TimestampMixin`.

### Settings (pydantic-settings)

Config lives in `src/config.py`. Each concern is a nested `BaseModel`:

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 30

class PostgresConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
    db: str = "app_db"
    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 50
    max_overflow: int = 10
    naming_convention: dict = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["config/.env", "config/.env.development"],
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="API__",
    )
    env: str = "development"
    run: RunConfig = RunConfig()
    logging: LogConfig = LogConfig()
    postgres: PostgresConfig = PostgresConfig()

settings = Settings()
```

Env vars use `__` delimiter: `API__POSTGRES__HOST`, `API__RUN__WORKERS`.

### Alembic (`migrations/env.py`)

Because `prepend_sys_path = ./src` is set in `alembic.ini`, imports in `env.py` use no prefix:

```python
from config import settings
from db import Base
import tasks.models  # noqa: F401 — register all models for autogenerate
```

Add a new domain's models import here every time a new module is created.

### Session / Database (`db/session.py`)

`session_getter` is the FastAPI dependency injected via `Annotated[AsyncSession, Depends(session_getter)]`. `dispose()` is called on app shutdown lifespan.

### Path Parameters

All path parameters **must** use `Annotated` + `Path()`:

```python
from typing import Annotated
from fastapi import Path

@router.get("/{task_id}")
async def get_task(task_id: Annotated[int, Path()]) -> TaskResponse:
    ...
```

### ORM Models

SQLAlchemy models use the `Orm` suffix: `TaskOrm`, `UserOrm`. Always use mixins:

```python
from db import Base, IdIntPkMixin, TimestampMixin

class TaskOrm(IdIntPkMixin, TimestampMixin, Base):
    __tablename__ = "tasks"
    ...
```

Router always converts ORM → Pydantic explicitly via `TaskResponse.model_validate(task)`.

## Testing

### Structure

```
tests/
├── conftest.py              # shared fixtures: session + client
└── <module>/
    ├── test_service.py      # unit: service functions called directly with session
    └── test_router.py       # integration: HTTP via AsyncClient
```

### pytest config (`pyproject.toml`)

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
```

`asyncio_mode = "auto"` means no `@pytest.mark.asyncio` decorator needed on any test.

### `tests/conftest.py`

Uses a real PostgreSQL database with **transaction rollback** after each test. Each test gets a fresh connection via `NullPool` (avoids asyncpg cross-event-loop issues — asyncpg connections cannot be shared across different event loops):

```python
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from config import settings
from main import app
from db import session_getter

import tasks.models  # noqa: F401


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(settings.postgres.url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.begin()
            async with AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as sess:
                yield sess
            await conn.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def override_session_getter():
        yield session

    app.dependency_overrides[session_getter] = override_session_getter

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()
```

`join_transaction_mode="create_savepoint"` — when service code calls `session.commit()`, it creates/releases a savepoint instead of a real commit, so the outer transaction stays active and is rolled back after the test.

**Important**: Every time a new domain model is added, import it in `conftest.py` (and `migrations/env.py`) to register it with `Base.metadata`.

### Writing tests

Unit test (service layer):
```python
async def test_create_task(session: AsyncSession):
    task = await create_task(session, TaskCreate(title="Test"))
    assert task.id is not None
```

Integration test (HTTP layer):
```python
async def test_create_task(client: AsyncClient):
    response = await client.post("/api/v1/tasks/", json={"title": "Test"})
    assert response.status_code == 201
```

## CI/CD (GitHub Actions)

Workflow lives in `.github/workflows/ci.yml`. Runs on every push/PR to `main`.

Two jobs:

**lint** — fails if code is not black-formatted:
```bash
uv run black src/ tests/ --check
```

**test** — spins up a postgres service, runs migrations, then pytest:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --group dev
      - run: uv run black src/ tests/ --check

  test:
    name: Tests
    runs-on: ubuntu-latest

    services:
      pg:
        image: postgres:15
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: prod_fastapi
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U postgres -d prod_fastapi"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --group dev
      - run: uv run alembic upgrade head
      - run: uv run pytest -v
```

Postgres credentials in `env:` are picked up automatically by pydantic-settings via `API__POSTGRES__*` prefix. No `.env` file needed in CI.

## Logging

`configure_logging()` in `src/logger.py` reads format from `settings.logging` and is called once at the top of `main.py` (before the `FastAPI` instance is created).

Declare per-module loggers at the top of each file:

```python
import logging

logger = logging.getLogger(__name__)
```

Always use `%`-style lazy formatting — never f-strings — in log calls:

```python
logger.info("created task %s", task.id)
logger.error("db error for task %s: %s", task_id, exc)
```