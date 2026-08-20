from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import session_getter

from .constants import DATABASE_ERROR_RESPONSE, NOT_FOUND_RESPONSE, VALIDATION_RESPONSE
from .dependencies import get_task_or_404
from .models import TaskOrm
from .schemas import TaskCreate, TaskResponse, TaskUpdate
from .service import create_task, delete_task, get_tasks, update_task

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    responses=DATABASE_ERROR_RESPONSE,
)


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> list[TaskResponse]:
    tasks = await get_tasks(session)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses=VALIDATION_RESPONSE,
)
async def create_task_route(
    data: TaskCreate,
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> TaskResponse:
    task = await create_task(session, data)
    return TaskResponse.model_validate(task)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    responses={**NOT_FOUND_RESPONSE, **VALIDATION_RESPONSE},
)
async def get_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
) -> TaskResponse:
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    responses={**NOT_FOUND_RESPONSE, **VALIDATION_RESPONSE},
)
async def update_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
    data: TaskUpdate,
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> TaskResponse:
    updated = await update_task(session, task, data)
    return TaskResponse.model_validate(updated)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND_RESPONSE, **VALIDATION_RESPONSE},
)
async def delete_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> None:
    await delete_task(session, task)
