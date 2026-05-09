import json
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends

from src import service
from src.auth import ActorDepend
from src.deps import IdemDepend, LLMDepend, RepoDepend
from src.guards import OwnedSessionDepend, verify_patch_ownership
from src.models import GuardrailCheck, Session
from src.schemas import PatchCreate, PatchProposalOut, PlanStepOut, SessionCreate

router = APIRouter()

logger = structlog.get_logger(__name__)


@router.post("/sessions", response_model=Session)
async def create_session(
    payload: SessionCreate,
    repo: RepoDepend,
    actor: ActorDepend,
) -> Session:
    return await service.create_session(payload, repo, actor)


@router.post("/sessions/{session_id}/plan", response_model=list[PlanStepOut])
async def create_plan(
    session: OwnedSessionDepend,
    repo: RepoDepend,
    llm_client: LLMDepend,
    idem: IdemDepend,
) -> list[PlanStepOut]:
    if idem.cached is not None:
        logger.info("plan_idempotent_hit")
        return [PlanStepOut.model_validate(item) for item in json.loads(idem.cached)]

    result = await service.create_plan(session, repo, llm_client)

    await repo.log_audit(
        trace_id=session.trace_id,
        actor=session.owner_id,
        action="create_plan",
        resource_type="session",
        resource_id=session.id,
    )
    if idem.key:
        await repo.set_idempotency(
            idem.key,
            json.dumps([r.model_dump(mode="json") for r in result]),
        )

    return result


@router.post("/sessions/{session_id}/patches", response_model=PatchProposalOut)
async def create_patch(
    session: OwnedSessionDepend,
    payload: PatchCreate,
    repo: RepoDepend,
    llm_client: LLMDepend,
    idem: IdemDepend,
) -> PatchProposalOut:
    if idem.cached is not None:
        logger.info("patch_idempotent_hit")
        return PatchProposalOut.model_validate(json.loads(idem.cached))

    result = await service.create_patch(session, payload, repo, llm_client)

    await repo.log_audit(
        trace_id=session.trace_id,
        actor=session.owner_id,
        action="create_patch",
        resource_type="patch",
        resource_id=result.id,
    )
    if idem.key:
        await repo.set_idempotency(
            idem.key,
            json.dumps(result.model_dump(mode="json")),
        )

    return result


@router.post(
    "/sessions/{session_id}/patches/{patch_id}/check",
    response_model=list[GuardrailCheck],
)
async def check_patch_in_session(
    patch_id: UUID,
    session: OwnedSessionDepend,
    repo: RepoDepend,
) -> list[GuardrailCheck]:
    return await service.check_patch_in_session(session, patch_id, repo)


@router.post("/patches/{patch_id}/check", response_model=list[GuardrailCheck])
async def check_patch(
    patch_id: UUID,
    repo: RepoDepend,
    _: Annotated[None, Depends(verify_patch_ownership)],
) -> list[GuardrailCheck]:
    return await service.check_patch(patch_id, repo)


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session: OwnedSessionDepend) -> Session:
    return session
