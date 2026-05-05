from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

async_engine = create_async_engine(
    url=settings.postgres.url,
    echo=settings.postgres.echo,
    echo_pool=settings.postgres.echo_pool,
    max_overflow=settings.postgres.max_overflow,
    pool_size=settings.postgres.pool_size,
)

session_factory = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def dispose() -> None:
    await async_engine.dispose()


async def session_getter() -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session
