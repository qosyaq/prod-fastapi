from fastapi import HTTPException, status


class TaskNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
