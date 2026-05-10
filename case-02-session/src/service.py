from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src import guardrails
from src.errors import NotFoundError
from src.llm import LLMProvider
from src.models import GuardrailCheck, PatchProposal, PlanStep, Session
from src.repository import SessionRepository
from src.schemas import (
    PatchCreate,
    PatchProposalOut,
    PlanStepInput,
    PlanStepOut,
    SessionCreate,
)

logger = structlog.get_logger(__name__)


async def create_session(
    payload: SessionCreate,
    repo: SessionRepository,
    actor: str,
) -> Session:
    session = Session(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        brand=payload.brand,
        trace_id=uuid4(),
        owner_id=actor,
        created_at=_now(),
    )
    saved = await repo.save_session(session)
    logger.info("session_created")
    return saved


async def create_plan(
    session: Session,
    repo: SessionRepository,
    llm_client: LLMProvider,
) -> list[PlanStepOut]:
    step_inputs = await llm_client.create_plan(
        session.title,
        session.description,
        session.brand,
    )
    steps = [_to_plan_step(step) for step in step_inputs]
    await repo.save_steps(session.id, steps)
    result = [PlanStepOut.model_validate(step) for step in steps]
    logger.info("plan_created", steps=len(result))
    return result


async def create_patch(
    session: Session,
    payload: PatchCreate,
    repo: SessionRepository,
    llm_client: LLMProvider,
) -> PatchProposalOut:
    step = await repo.find_step(session.id, payload.step_id)
    if step is None:
        raise NotFoundError("step not found")

    patch_id = uuid4()
    patch_input = await llm_client.create_patch(
        _to_plan_step_input(step), session.brand
    )
    patch = _to_patch(session, payload.step_id, patch_input.diff, patch_id)
    stored = await repo.save_patch(session.id, patch)
    if stored is None:
        raise NotFoundError("step not found")

    result = PatchProposalOut.model_validate(stored)
    logger.info("patch_created", patch_id=str(stored.id))
    return result


async def check_patch_in_session(
    session: Session,
    patch_id: UUID,
    repo: SessionRepository,
) -> list[GuardrailCheck]:
    if not await repo.patch_belongs_to_session(session.id, patch_id):
        raise NotFoundError("patch not found in session")
    return await _run_patch_checks(patch_id, repo)


async def check_patch(
    patch_id: UUID,
    repo: SessionRepository,
) -> list[GuardrailCheck]:
    return await _run_patch_checks(patch_id, repo)


async def _run_patch_checks(
    patch_id: UUID,
    repo: SessionRepository,
) -> list[GuardrailCheck]:
    patch = await repo.get_patch(patch_id)
    if patch is None:
        raise NotFoundError("patch not found")
    checks = guardrails.run_checks(patch.diff, patch.brand)
    stored = await repo.save_checks(patch_id, checks)
    if stored is None:
        raise NotFoundError("patch not found")
    return stored


def _to_plan_step(step: PlanStepInput) -> PlanStep:
    return PlanStep(
        id=uuid4(),
        description=step.description,
        target_files=step.target_files,
    )


def _to_plan_step_input(step: PlanStep) -> PlanStepInput:
    return PlanStepInput(description=step.description, target_files=step.target_files)


def _to_patch(
    session: Session,
    step_id: UUID,
    diff: str,
    patch_id: UUID | None = None,
) -> PatchProposal:
    return PatchProposal(
        id=patch_id or uuid4(),
        step_id=step_id,
        brand=session.brand,
        diff=diff,
        created_at=_now(),
    )


def _now() -> datetime:
    return datetime.now(UTC)
