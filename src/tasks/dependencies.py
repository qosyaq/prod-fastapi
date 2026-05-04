from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from db import session_getter
from .exceptions import TaskNotFound
from .models import TaskOrm
from .service import get_task_by_id


async def get_task_or_404(
    task_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(session_getter)],
) -> TaskOrm:
    task = await get_task_by_id(session, task_id)
    if not task:
        raise TaskNotFound()
    return task
