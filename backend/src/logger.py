import logging

from src.config import settings

_cfg = settings.logging


class _EndpointFilter(logging.Filter):
    """Suppress noisy access log entries for internal endpoints."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


def configure_logging() -> None:
    if settings.observability_enabled:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(fmt=_cfg.fmt_otlp))
        logging.basicConfig(level=_cfg.level, handlers=[handler])
        logging.getLogger("uvicorn.access").addFilter(_EndpointFilter())
    else:
        logging.basicConfig(level=_cfg.level, format=_cfg.fmt)
