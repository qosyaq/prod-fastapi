from .logger import GunicornLogger


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
    }
