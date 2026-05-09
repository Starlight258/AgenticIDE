"""Authorization guards — enforce ownership before route handlers run."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends

from src.auth import ActorDepend
from src.deps import RepoDepend
from src.errors import NotFoundError, OwnershipError
from src.models import Session


async def get_owned_session(
    session_id: UUID,
    repo: RepoDepend,
    actor: ActorDepend,
) -> Session:
    session = await repo.get_session(session_id)
    if session is None:
        raise NotFoundError("session not found")
    if session.owner_id != actor:
        raise OwnershipError("session does not belong to actor")
    structlog.contextvars.bind_contextvars(
        actor=actor,
        session_id=str(session.id),
        trace_id=str(session.trace_id),
    )
    return session


OwnedSessionDepend = Annotated[Session, Depends(get_owned_session)]


async def verify_patch_ownership(
    patch_id: UUID,
    repo: RepoDepend,
    actor: ActorDepend,
) -> None:
    owner = await repo.get_patch_owner(patch_id)
    if owner is None:
        raise NotFoundError("patch not found")
    if owner != actor:
        raise OwnershipError("session does not belong to actor")
