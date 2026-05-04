import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from config import settings
from logger import configure_logging
from exceptions import register_exception_handlers
from db import dispose
from router import router

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

app.include_router(router)
