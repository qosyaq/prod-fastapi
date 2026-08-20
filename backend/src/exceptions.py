import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.errors import ErrorCode, ErrorItem, ErrorResponse, code_for_status

log = logging.getLogger(__name__)


class AppException(Exception):
    """Базовое исключение приложения с явным статус-кодом и списком ошибок."""

    def __init__(self, status_code: int, errors: list[ErrorItem]):
        super().__init__("; ".join(e.message for e in errors))
        self.status_code = status_code
        self.errors = errors


def _response(status_code: int, errors: list[ErrorItem]) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=ErrorResponse(errors=errors).model_dump()
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        log_fn = log.error if exc.status_code >= 500 else log.warning
        log_fn("AppException: %s", exc.errors)
        return _response(exc.status_code, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            ErrorItem(
                code=ErrorCode.VALIDATION_ERROR,
                message=err["msg"],
                field=".".join(str(x) for x in err["loc"] if x != "body") or None,
            )
            for err in exc.errors()
        ]
        return _response(status.HTTP_422_UNPROCESSABLE_ENTITY, errors)

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        log.exception("Database error")
        errors = [ErrorItem(code=ErrorCode.DATABASE_ERROR, message="Database error")]
        return _response(status.HTTP_503_SERVICE_UNAVAILABLE, errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        errors = [
            ErrorItem(code=code_for_status(exc.status_code), message=str(exc.detail))
        ]
        return _response(exc.status_code, errors)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        log.exception("Unhandled exception")
        errors = [
            ErrorItem(code=ErrorCode.INTERNAL_ERROR, message="Internal server error")
        ]
        return _response(status.HTTP_500_INTERNAL_SERVER_ERROR, errors)
