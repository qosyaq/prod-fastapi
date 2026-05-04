import logging

from config import settings

def configure_logging() -> None:
    logging.basicConfig(
        level=settings.logging.level,
        format=settings.logging.fmt,
        datefmt=settings.logging.datefmt,
    )