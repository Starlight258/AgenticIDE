from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog

from src import guardrails
from src.errors import APIError, AlreadyCheckedError
from src.llm import LLMProvider
from src.models import GuardrailCheck, PatchProposal, PlanStep, Session, TestRun
from src.repository import SessionRepository
from src.schemas import (
    PatchCreate,
    PatchProposalOut,
    PlanStepInput,
    PlanStepOut,
    SessionCreate,
    StepReadinessOut,
    TestRunCreate,
    TestRunOut,
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
    return await create_patch_for_step(session, payload.step_id, repo, llm_client)


async def create_patch_for_step(
    session: Session,
    step_id: UUID,
    repo: SessionRepository,
    llm_client: LLMProvider,
) -> PatchProposalOut:
    step = await repo.find_step(session.id, step_id)
    if step is None:
        raise APIError(
            404,
            "step_not_found",
            f"Step {step_id} not found in session {session.id}",
        )

    patch_id = uuid4()
    patch_input = await llm_client.create_patch(
        _to_plan_step_input(step), session.brand
    )
    patch = _to_patch(session, step_id, patch_input.diff, patch_id)
    stored = await repo.save_patch(session.id, patch)
    if stored is None:
        raise APIError(
            404,
            "step_not_found",
            f"Step {step_id} not found in session {session.id}",
        )

    result = PatchProposalOut.model_validate(stored)
    logger.info("patch_created", patch_id=str(stored.id))
    return result


async def check_patch_in_session(
    session: Session,
    patch_id: UUID,
    repo: SessionRepository,
) -> list[GuardrailCheck]:
    if not await repo.patch_belongs_to_session(session.id, patch_id):
        raise APIError(
            404,
            "patch_not_found",
            f"Patch {patch_id} not found in session {session.id}",
        )
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
        raise APIError(404, "patch_not_found", f"Patch {patch_id} not found")
    if patch.checks:
        raise AlreadyCheckedError(patch_id, patch.checks)

    checks = guardrails.run_checks(patch.diff, patch.brand)
    updated = await repo.update_patch_if_version(patch_id, patch.version, checks)
    if updated:
        return checks

    latest = await repo.get_patch(patch_id)
    if latest is not None and latest.checks:
        raise AlreadyCheckedError(patch_id, latest.checks)
    raise APIError(409, "version_conflict", f"Patch {patch_id} changed during check")


async def get_step_readiness(
    session: Session,
    step_id: UUID,
    repo: SessionRepository,
) -> StepReadinessOut:
    step = await _get_full_step(session.id, step_id, repo)
    latest_patch = max(step.patches, key=lambda patch: patch.created_at, default=None)
    if latest_patch is None or not latest_patch.checks:
        return StepReadinessOut(
            step_id=step_id,
            verdict="NOT_READY",
            block_count=0,
            warn_count=0,
            latest_patch_id=latest_patch.id if latest_patch else None,
        )

    block_count = _count_checks(latest_patch.checks, "BLOCK")
    warn_count = _count_checks(latest_patch.checks, "WARN")
    verdict = "NOT_READY" if block_count else "READY"
    return StepReadinessOut(
        step_id=step_id,
        verdict=verdict,
        block_count=block_count,
        warn_count=warn_count,
        latest_patch_id=latest_patch.id,
    )


async def create_test_run(
    session: Session,
    payload: TestRunCreate,
    repo: SessionRepository,
) -> TestRunOut:
    for patch_id in payload.patch_ids:
        patch = await repo.get_patch(patch_id)
        if patch is None:
            raise APIError(
                422,
                "patch_not_found_in_payload",
                f"Patch {patch_id} does not exist",
                patch_id=str(patch_id),
            )
        if not await repo.patch_belongs_to_session(session.id, patch_id):
            raise APIError(
                422,
                "patch_not_in_session",
                f"Patch {patch_id} is not in session {session.id}",
                patch_id=str(patch_id),
            )

    test_run = TestRun(
        id=uuid4(),
        session_id=session.id,
        patch_ids=payload.patch_ids,
        outcome=payload.outcome,
        notes=payload.notes,
        created_at=_now(),
    )
    stored = await repo.save_test_run(session.id, test_run)
    if stored is None:
        raise APIError(
            404,
            "session_not_found",
            f"Session {session.id} not found",
        )
    return TestRunOut.model_validate(stored)


async def _get_full_step(
    session_id: UUID,
    step_id: UUID,
    repo: SessionRepository,
) -> PlanStep:
    session = await repo.get_session(session_id)
    if session is None:
        raise APIError(404, "session_not_found", f"Session {session_id} not found")
    step = next((item for item in session.steps if item.id == step_id), None)
    if step is None:
        raise APIError(
            404,
            "step_not_found",
            f"Step {step_id} not found in session {session_id}",
        )
    return step


def _count_checks(checks: list[GuardrailCheck], severity: str) -> int:
    return sum(
        check.result == "fail" and check.severity == severity for check in checks
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
