from fastapi import APIRouter

from src.tasks import tasks_router

router = APIRouter(prefix="/api/v1")
router.include_router(tasks_router)
