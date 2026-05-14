import logging

from config import settings


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=settings.logging.fmt))
    logging.basicConfig(level=settings.logging.level, handlers=[handler])
