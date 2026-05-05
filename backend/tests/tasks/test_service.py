import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tasks.constants import TaskStatus
from tasks.schemas import TaskCreate, TaskUpdate
from tasks.service import (
    create_task,
    delete_task,
    get_task_by_id,
    get_tasks,
    update_task,
)


async def test_create_task(session: AsyncSession):
    data = TaskCreate(title="Test task")
    task = await create_task(session, data)

    assert task.id is not None
    assert task.title == "Test task"
    assert task.description is None
    assert task.status == TaskStatus.PENDING


async def test_create_task_with_all_fields(session: AsyncSession):
    data = TaskCreate(
        title="Full task", description="Desc", status=TaskStatus.IN_PROGRESS
    )
    task = await create_task(session, data)

    assert task.title == "Full task"
    assert task.description == "Desc"
    assert task.status == TaskStatus.IN_PROGRESS


async def test_get_tasks_empty(session: AsyncSession):
    tasks = await get_tasks(session)
    assert tasks == []


async def test_get_tasks_returns_all(session: AsyncSession):
    await create_task(session, TaskCreate(title="Task 1"))
    await create_task(session, TaskCreate(title="Task 2"))

    tasks = await get_tasks(session)
    assert len(tasks) == 2
    assert [t.title for t in tasks] == ["Task 1", "Task 2"]


async def test_get_tasks_ordered_by_id(session: AsyncSession):
    await create_task(session, TaskCreate(title="B"))
    await create_task(session, TaskCreate(title="A"))

    tasks = await get_tasks(session)
    assert tasks[0].id <= tasks[1].id


async def test_get_task_by_id(session: AsyncSession):
    created = await create_task(session, TaskCreate(title="Find me"))
    found = await get_task_by_id(session, created.id)

    assert found is not None
    assert found.id == created.id
    assert found.title == "Find me"


async def test_get_task_by_id_not_found(session: AsyncSession):
    result = await get_task_by_id(session, 99999)
    assert result is None


async def test_update_task_title(session: AsyncSession):
    task = await create_task(session, TaskCreate(title="Old"))
    updated = await update_task(session, task, TaskUpdate(title="New"))

    assert updated.title == "New"
    assert updated.status == TaskStatus.PENDING


async def test_update_task_status(session: AsyncSession):
    task = await create_task(session, TaskCreate(title="Task"))
    updated = await update_task(session, task, TaskUpdate(status=TaskStatus.DONE))

    assert updated.status == TaskStatus.DONE
    assert updated.title == "Task"


async def test_update_task_partial(session: AsyncSession):
    task = await create_task(session, TaskCreate(title="Task", description="Desc"))
    updated = await update_task(
        session, task, TaskUpdate(status=TaskStatus.IN_PROGRESS)
    )

    assert updated.description == "Desc"
    assert updated.status == TaskStatus.IN_PROGRESS


async def test_delete_task(session: AsyncSession):
    task = await create_task(session, TaskCreate(title="To delete"))
    task_id = task.id

    await delete_task(session, task)

    assert await get_task_by_id(session, task_id) is None


@pytest.mark.parametrize("status", list(TaskStatus))
async def test_create_task_all_statuses(session: AsyncSession, status: TaskStatus):
    task = await create_task(session, TaskCreate(title="Task", status=status))
    assert task.status == status
