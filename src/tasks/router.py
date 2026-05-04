from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from db import session_getter
from .dependencies import get_task_or_404
from .models import TaskOrm
from .schemas import TaskCreate, TaskResponse, TaskUpdate
from .service import create_task, delete_task, get_tasks, update_task

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> list[TaskResponse]:
    tasks = await get_tasks(session)
    return [TaskResponse.model_validate(task) for task in tasks]


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task_route(
    data: TaskCreate,
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> TaskResponse:
    task = await create_task(session, data)
    return TaskResponse.model_validate(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
) -> TaskResponse:
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
    data: TaskUpdate,
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> TaskResponse:
    updated = await update_task(session, task, data)
    return TaskResponse.model_validate(updated)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_route(
    task: Annotated[TaskOrm, Depends(get_task_or_404)],
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> None:
    await delete_task(session, task)
