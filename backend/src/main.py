import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.db import dispose
from src.exceptions import register_exception_handlers
from src.logger import configure_logging
from src.observability import setup_observability
from src.router import router

configure_logging()
log = logging.getLogger(__name__)


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

if settings.observability_enabled:
    setup_observability(app)

app.include_router(router)
