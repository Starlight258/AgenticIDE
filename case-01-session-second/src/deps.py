from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db import get_session
from src.llm import AnthropicLLM, LLMProvider
from src.repository import SQLiteRepository


async def _get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session(settings.db_url):
        yield session


def get_repo(
    session: Annotated[AsyncSession, Depends(_get_db_session)],
) -> SQLiteRepository:
    return SQLiteRepository(session)


def get_llm() -> LLMProvider:
    return AnthropicLLM()


RepoDepend = Annotated[SQLiteRepository, Depends(get_repo)]
SettingsDepend = Annotated[Settings, Depends(get_settings)]
LLMDepend = Annotated[LLMProvider, Depends(get_llm)]
