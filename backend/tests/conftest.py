import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import settings
from src.db import session_getter
from src.main import app


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(settings.postgres.url, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.begin()
            async with AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as sess:
                yield sess
            await conn.rollback()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(session: AsyncSession):
    async def override_session_getter():
        yield session

    app.dependency_overrides[session_getter] = override_session_getter

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()
