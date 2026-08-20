from enum import StrEnum

from src.errors import ErrorResponse


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


VALIDATION_RESPONSE = {422: {"model": ErrorResponse}}
NOT_FOUND_RESPONSE = {404: {"model": ErrorResponse}}
DATABASE_ERROR_RESPONSE = {503: {"model": ErrorResponse}}
