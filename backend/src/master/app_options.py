from .logger import GunicornLogger


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
