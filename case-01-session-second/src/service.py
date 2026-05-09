from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src import guardrails
from src.config import Settings
from src.llm import LLMProvider
from src.models import (
    GuardrailCheck,
    PatchCreate,
    PatchProposal,
    PatchProposalOut,
    PlanStep,
    PlanStepInput,
    PlanStepOut,
    Session,
    SessionCreate,
)
from src.repository import SessionRepository

logger = structlog.get_logger(__name__)


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass


async def create_session(
    payload: SessionCreate,
    repo: SessionRepository,
    actor: str = "",
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
    _bind_log_context(saved, actor)
    logger.info("session_created")
    return saved


async def create_plan(
    session_id: UUID,
    repo: SessionRepository,
    llm_client: LLMProvider,
    settings: Settings,
    actor: str = "",
    idempotency_key: str | None = None,
) -> list[PlanStepOut]:
    session = await _require_owned_session(session_id, repo, actor)
    _bind_log_context(session, actor)

    # Idempotency check
    if idempotency_key:
        cached = await repo.get_idempotency(idempotency_key)
        if cached is not None:
            import json

            logger.info("plan_idempotent_hit")
            raw = json.loads(cached)
            return [PlanStepOut.model_validate(item) for item in raw]

    step_inputs = await llm_client.create_plan(
        session.title, session.description, session.brand, settings
    )
    await repo.log_audit(
        trace_id=session.trace_id,
        actor=actor,
        action="create_plan",
        resource_type="session",
        resource_id=session.id,
    )
    steps = [_to_plan_step(step) for step in step_inputs]
    await repo.save_steps(session_id, steps)
    result = [PlanStepOut.model_validate(step) for step in steps]
    logger.info("plan_created", steps=len(result))

    if idempotency_key:
        import json

        await repo.set_idempotency(
            idempotency_key,
            json.dumps([r.model_dump(mode="json") for r in result]),
        )

    return result


async def create_patch(
    session_id: UUID,
    payload: PatchCreate,
    repo: SessionRepository,
    llm_client: LLMProvider,
    settings: Settings,
    actor: str = "",
    idempotency_key: str | None = None,
) -> PatchProposalOut:
    session = await _require_owned_session(session_id, repo, actor)
    _bind_log_context(session, actor)

    # Idempotency check
    if idempotency_key:
        cached = await repo.get_idempotency(idempotency_key)
        if cached is not None:
            import json

            logger.info("patch_idempotent_hit")
            return PatchProposalOut.model_validate(json.loads(cached))

    step = await repo.find_step(session_id, payload.step_id)
    if step is None:
        raise NotFoundError("step not found")

    patch_id = uuid4()
    patch_input = await llm_client.create_patch(
        _to_plan_step_input(step), session.brand, settings
    )
    await repo.log_audit(
        trace_id=session.trace_id,
        actor=actor,
        action="create_patch",
        resource_type="patch",
        resource_id=patch_id,
    )
    patch = _to_patch(session, payload.step_id, patch_input.diff, patch_id)
    stored = await repo.save_patch(session_id, patch)
    if stored is None:
        raise NotFoundError("step not found")

    result = PatchProposalOut.model_validate(stored)
    logger.info("patch_created", patch_id=str(stored.id))

    if idempotency_key:
        import json

        await repo.set_idempotency(
            idempotency_key,
            json.dumps(result.model_dump(mode="json")),
        )

    return result


async def check_patch_in_session(
    session_id: UUID,
    patch_id: UUID,
    repo: SessionRepository,
    actor: str = "",
) -> list[GuardrailCheck]:
    session = await _require_owned_session(session_id, repo, actor)
    _bind_log_context(session, actor)
    if not await repo.patch_belongs_to_session(session_id, patch_id):
        raise NotFoundError("patch not found in session")
    return await _run_patch_checks(patch_id, repo)


async def check_patch(
    patch_id: UUID,
    repo: SessionRepository,
    actor: str = "",
) -> list[GuardrailCheck]:
    owner = await repo.get_patch_owner(patch_id)
    if owner is None:
        raise NotFoundError("patch not found")
    if owner != actor:
        raise OwnershipError("session does not belong to actor")
    logger.info("patch_check_requested", actor=actor, patch_id=str(patch_id))
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


async def get_session(
    session_id: UUID,
    repo: SessionRepository,
    actor: str = "",
) -> Session:
    session = await _require_owned_session(session_id, repo, actor)
    _bind_log_context(session, actor)
    logger.info("session_loaded")
    return session


async def _require_session(session_id: UUID, repo: SessionRepository) -> Session:
    session = await repo.get_session(session_id)
    if session is None:
        raise NotFoundError("session not found")
    return session


async def _require_owned_session(
    session_id: UUID,
    repo: SessionRepository,
    actor: str,
) -> Session:
    session = await _require_session(session_id, repo)
    if session.owner_id != actor:
        raise OwnershipError("session does not belong to actor")
    return session


def _bind_log_context(session: Session, actor: str) -> None:
    structlog.contextvars.bind_contextvars(
        actor=actor,
        session_id=str(session.id),
        trace_id=str(session.trace_id),
    )


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
