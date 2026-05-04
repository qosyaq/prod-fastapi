from config import settings
from master import Application, get_app_options
from main import app


def main() -> None:
    Application(
        application=app,
        options=get_app_options(
            host=settings.run.host,
            port=settings.run.port,
            timeout=settings.run.timeout,
            workers=settings.run.workers,
            log_level=settings.logging.level,
        ),
    ).run()


if __name__ == "__main__":
    main()
