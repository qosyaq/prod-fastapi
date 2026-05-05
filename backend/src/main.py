import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import CollectorRegistry, make_asgi_app, multiprocess
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from db import dispose
from exceptions import register_exception_handlers
from logger import configure_logging
from router import router

configure_logging()
log = logging.getLogger(__name__)


def _make_metrics_app():
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return make_asgi_app(registry=registry)
    return make_asgi_app()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    log.info("Application Started")
    yield
    log.info("Closing all connections...")
    await dispose()
    log.info("Application Shutdown")


app = FastAPI(
    title=settings.title,
    description=settings.description,
    version=settings.version,
    debug=settings.debug,
    lifespan=lifespan,
)

register_exception_handlers(app)
Instrumentator().instrument(app)

app.include_router(router)
app.mount("/metrics", _make_metrics_app())
