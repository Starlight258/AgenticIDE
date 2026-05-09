from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from src import service
from src.auth import get_current_actor
from src.deps import LLMDepend, RepoDepend, SettingsDepend
from src.models import (
    GuardrailCheck,
    PatchCreate,
    PatchProposalOut,
    PlanStepOut,
    Session,
    SessionCreate,
)

router = APIRouter()

ActorDepend = Annotated[str, Depends(get_current_actor)]


@router.post("/sessions", response_model=Session)
async def create_session(
    payload: SessionCreate,
    repo: RepoDepend,
    actor: ActorDepend,
) -> Session:
    created = await service.create_session(payload, repo, actor)
    return Session.model_validate(created)


@router.post("/sessions/{session_id}/plan", response_model=list[PlanStepOut])
async def create_plan(
    session_id: UUID,
    repo: RepoDepend,
    llm_client: LLMDepend,
    settings: SettingsDepend,
    actor: ActorDepend,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> list[PlanStepOut]:
    return await service.create_plan(
        session_id,
        repo,
        llm_client,
        settings,
        actor=actor,
        idempotency_key=idempotency_key,
    )


@router.post("/sessions/{session_id}/patches", response_model=PatchProposalOut)
async def create_patch(
    session_id: UUID,
    payload: PatchCreate,
    repo: RepoDepend,
    llm_client: LLMDepend,
    settings: SettingsDepend,
    actor: ActorDepend,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> PatchProposalOut:
    return await service.create_patch(
        session_id,
        payload,
        repo,
        llm_client,
        settings,
        actor=actor,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/sessions/{session_id}/patches/{patch_id}/check",
    response_model=list[GuardrailCheck],
)
async def check_patch_in_session(
    session_id: UUID,
    patch_id: UUID,
    repo: RepoDepend,
    actor: ActorDepend,
) -> list[GuardrailCheck]:
    return await service.check_patch_in_session(session_id, patch_id, repo, actor)


@router.post("/patches/{patch_id}/check", response_model=list[GuardrailCheck])
async def check_patch(
    patch_id: UUID,
    repo: RepoDepend,
    actor: ActorDepend,
) -> list[GuardrailCheck]:
    return await service.check_patch(patch_id, repo, actor)


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(
    session_id: UUID,
    repo: RepoDepend,
    actor: ActorDepend,
) -> Session:
    return Session.model_validate(await service.get_session(session_id, repo, actor))
