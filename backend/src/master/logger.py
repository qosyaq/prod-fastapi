from logging import Formatter

from gunicorn.glogging import Logger

from config import settings


class GunicornLogger(Logger):
    def setup(self, cfg) -> None:
        super().setup(cfg)
        fmt = Formatter(fmt=settings.logging.fmt, datefmt=settings.logging.datefmt)
        self._set_handler(self.access_log, cfg.accesslog, fmt)
        self._set_handler(self.error_log, cfg.errorlog, fmt)
