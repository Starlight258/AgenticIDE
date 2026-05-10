from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

_engine = None


def get_engine(db_url: str):
    global _engine
    if _engine is None:
        _engine = create_async_engine(db_url, echo=False)
    return _engine


async def create_tables(db_url: str) -> None:
    engine = get_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session(db_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = get_engine(db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
