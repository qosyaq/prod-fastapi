from fastapi import status

from src.errors import ErrorCode, ErrorItem
from src.exceptions import AppException


class TaskNotFound(AppException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            errors=[ErrorItem(code=ErrorCode.NOT_FOUND, message="Task not found")],
        )
