from datetime import UTC, datetime
from uuid import UUID, uuid4

from src import guardrails, llm, store
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


class NotFoundError(Exception):
    pass


def create_session(payload: SessionCreate) -> Session:
    session = Session(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        brand=payload.brand,
        trace_id=uuid4(),
        created_at=_now(),
    )
    return store.save_session(session)


def create_plan(session_id: UUID) -> list[PlanStepOut]:
    session = _require_session(session_id)
    step_inputs = llm.create_plan(session.title, session.description, session.brand)
    steps = [_to_plan_step(step) for step in step_inputs]
    store.save_steps(session_id, steps)
    return [PlanStepOut.model_validate(step) for step in steps]


def create_patch(session_id: UUID, payload: PatchCreate) -> PatchProposalOut:
    session = _require_session(session_id)
    step = store.find_step(session_id, payload.step_id)
    if step is None:
        raise NotFoundError("step not found")
    patch_input = llm.create_patch(_to_plan_step_input(step))
    patch = _to_patch(session, payload.step_id, patch_input.diff)
    stored = store.save_patch(session_id, patch)
    if stored is None:
        raise NotFoundError("step not found")
    return PatchProposalOut.model_validate(stored)


def check_patch(patch_id: UUID) -> list[GuardrailCheck]:
    patch = store.get_patch(patch_id)
    if patch is None:
        raise NotFoundError("patch not found")
    checks = guardrails.run_checks(patch.diff)
    stored = store.save_checks(patch_id, checks)
    if stored is None:
        raise NotFoundError("patch not found")
    return stored


def get_session(session_id: UUID) -> Session:
    return _require_session(session_id)


def _require_session(session_id: UUID) -> Session:
    session = store.get_session(session_id)
    if session is None:
        raise NotFoundError("session not found")
    return session


def _to_plan_step(step: PlanStepInput) -> PlanStep:
    return PlanStep(
        id=uuid4(),
        description=step.description,
        target_files=step.target_files,
    )


def _to_plan_step_input(step: PlanStep) -> PlanStepInput:
    return PlanStepInput(description=step.description, target_files=step.target_files)


def _to_patch(session: Session, step_id: UUID, diff: str) -> PatchProposal:
    return PatchProposal(
        id=uuid4(),
        step_id=step_id,
        brand=session.brand,
        diff=diff,
        created_at=_now(),
    )


def _now() -> datetime:
    return datetime.now(UTC)
