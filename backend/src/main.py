import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.db import dispose
from src.exceptions import register_exception_handlers
from src.logger import configure_logging
from src.observability_utils import PrometheusMiddleware, metrics, setting_otlp
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
app.add_middleware(PrometheusMiddleware, app_name=settings.observability.app_name)
app.add_route("/metrics", metrics)
setting_otlp(
    app, settings.observability.app_name, settings.observability.otlp_grpc_endpoint
)


class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

app.include_router(router)
