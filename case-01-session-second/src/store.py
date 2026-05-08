from uuid import UUID

from src.models import GuardrailCheck, PatchProposal, PlanStep, Session

_sessions: dict[UUID, Session] = {}
_patches: dict[UUID, PatchProposal] = {}


def clear() -> None:
    _sessions.clear()
    _patches.clear()


def save_session(session: Session) -> Session:
    _sessions[session.id] = session
    return session


def get_session(session_id: UUID) -> Session | None:
    return _sessions.get(session_id)


def save_steps(session_id: UUID, steps: list[PlanStep]) -> list[PlanStep] | None:
    session = get_session(session_id)
    if session is None:
        return None
    session.steps = steps
    return session.steps


def find_step(session_id: UUID, step_id: UUID) -> PlanStep | None:
    session = get_session(session_id)
    if session is None:
        return None
    return next((step for step in session.steps if step.id == step_id), None)


def save_patch(session_id: UUID, patch: PatchProposal) -> PatchProposal | None:
    step = find_step(session_id, patch.step_id)
    if step is None:
        return None
    step.patches.append(patch)
    _patches[patch.id] = patch
    return patch


def get_patch(patch_id: UUID) -> PatchProposal | None:
    return _patches.get(patch_id)


def save_checks(
    patch_id: UUID,
    checks: list[GuardrailCheck],
) -> list[GuardrailCheck] | None:
    patch = get_patch(patch_id)
    if patch is None:
        return None
    patch.checks = checks
    return patch.checks
