"""Infrastructure dependencies — repo, llm, settings, idempotency."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, get_settings
from src.db import get_session
from src.llm import AnthropicLLM, LLMProvider
from src.sqlite_repository import SQLiteRepository


async def _get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session(settings.db_url):
        yield session


def get_repo(
    session: Annotated[AsyncSession, Depends(_get_db_session)],
) -> SQLiteRepository:
    return SQLiteRepository(session)


SettingsDepend = Annotated[Settings, Depends(get_settings)]


def get_llm(settings: SettingsDepend) -> LLMProvider:
    return AnthropicLLM(settings)


RepoDepend = Annotated[SQLiteRepository, Depends(get_repo)]
LLMDepend = Annotated[LLMProvider, Depends(get_llm)]


@dataclass
class IdempotencyContext:
    key: str | None
    cached: str | None  # JSON-serialized response; None = cache miss


async def get_idempotency(
    repo: RepoDepend,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> IdempotencyContext:
    if idempotency_key:
        cached = await repo.get_idempotency(idempotency_key)
        if cached is not None:
            return IdempotencyContext(key=idempotency_key, cached=cached)
    return IdempotencyContext(key=idempotency_key, cached=None)


IdemDepend = Annotated[IdempotencyContext, Depends(get_idempotency)]
