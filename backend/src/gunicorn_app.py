import logging

from fastapi import FastAPI
from gunicorn.app.base import BaseApplication
from gunicorn.glogging import Logger

from src.config import settings


class GunicornLogger(Logger):
    def setup(self, cfg) -> None:
        super().setup(cfg)
        fmt = logging.Formatter(fmt=settings.logging.fmt)
        self._set_handler(self.access_log, cfg.accesslog, fmt)
        self._set_handler(self.error_log, cfg.errorlog, fmt)


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


def _child_exit(server, worker) -> None:
    from prometheus_client import multiprocess

    multiprocess.mark_process_dead(worker.pid)


def get_app_options(
    host: str,
    port: int,
    timeout: int,
    workers: int,
    log_level: str,
) -> dict:
    return {
        "bind": f"{host}:{port}",
        "workers": workers,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "timeout": timeout,
        "loglevel": log_level,
        "accesslog": "-",
        "errorlog": "-",
        "logger_class": GunicornLogger,
        "child_exit": _child_exit,
    }