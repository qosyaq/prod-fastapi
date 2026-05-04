import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import TaskOrm
from .schemas import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


async def get_tasks(session: AsyncSession) -> list[TaskOrm]:
    result = await session.execute(select(TaskOrm).order_by(TaskOrm.id))
    return list(result.scalars().all())


async def get_task_by_id(session: AsyncSession, task_id: int) -> TaskOrm | None:
    return await session.get(TaskOrm, task_id)


async def create_task(session: AsyncSession, data: TaskCreate) -> TaskOrm:
    task = TaskOrm(**data.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    logger.info("created task %s", task.id)
    return task


async def update_task(session: AsyncSession, task: TaskOrm, data: TaskUpdate) -> TaskOrm:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    logger.info("updated task %s", task.id)
    return task


async def delete_task(session: AsyncSession, task: TaskOrm) -> None:
    await session.delete(task)
    await session.commit()
    logger.info("deleted task %s", task.id)
