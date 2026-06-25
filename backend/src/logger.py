import logging

from src.config import settings
from src.constants import Environment

_cfg = settings.logging


class _EndpointFilter(logging.Filter):
    """Suppress noisy access log entries for internal endpoints."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


def configure_logging() -> None:
    if settings.env == Environment.development:
        logging.basicConfig(
            level=_cfg.level,
            format=_cfg.fmt,
        )
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt=settings.logging.fmt))
        logging.basicConfig(level=settings.logging.level, handlers=[handler])
        if settings.observability_enabled:
            logging.getLogger("uvicorn.access").addFilter(_EndpointFilter())
