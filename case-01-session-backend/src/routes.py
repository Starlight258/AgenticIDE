"""FastAPI route definitions for session, plan, patch, and guardrail check endpoints."""
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src import llm
from src.models import (
    Brand,
    GuardrailCheck,
    PatchProposal,
    PatchProposalInput,
    PatchProposalOut,
    PlanStep,
    PlanStepInput,
    PlanStepOut,
    Session,
)
from src.store import sessions

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateSessionBody(BaseModel):
    title: str
    description: str
    brand: Brand


@router.post("/sessions", response_model=Session)
def create_session(body: CreateSessionBody) -> Session:
    """Create and store a new session."""
    session = Session(title=body.title, description=body.description, brand=body.brand)
    sessions[str(session.id)] = session
    logger.info("Created session %s for brand %s", session.id, session.brand)
    return session


@router.post("/sessions/{session_id}/plan", response_model=list[PlanStepOut])
def create_plan(session_id: UUID) -> list[PlanStepOut]:
    """Generate a plan for the session and attach steps."""
    session = _get_session(session_id)
    prompt = (
        f"Create a plan for: {session.description}\n"
        "Respond with a JSON array of PlanStep objects."
    )
    raw_steps = llm.generate_list(prompt, session.brand, PlanStepInput)
    steps = [PlanStep(**step) for step in raw_steps]
    session.steps = steps
    logger.info("Generated %d plan steps for session %s", len(steps), session_id)
    return [PlanStepOut(id=s.id, description=s.description, target_files=s.target_files) for s in steps]


@router.post("/sessions/{session_id}/steps/{step_id}/patches", response_model=PatchProposalOut)
def create_patch(session_id: UUID, step_id: UUID) -> PatchProposalOut:
    """Generate a patch proposal for a plan step."""
    session = _get_session(session_id)
    step = _get_step(session, str(step_id))
    prompt = (
        f"Generate a unified diff patch for: {step.description}\n"
        f"Target files: {step.target_files}"
    )
    raw = llm.generate(prompt, session.brand, PatchProposalInput)
    raw["planStepId"] = str(step.id)
    patch = PatchProposal(**raw)
    step.patches.append(patch)
    logger.info("Generated patch %s for step %s", patch.id, step.id)
    return PatchProposalOut(id=patch.id, planStepId=patch.planStepId, diff=patch.diff, created_at=patch.created_at)


@router.post(
    "/sessions/{session_id}/steps/{step_id}/patches/{patch_id}/check",
    response_model=list[GuardrailCheck],
)
def check_patch(session_id: UUID, step_id: UUID, patch_id: UUID) -> list[GuardrailCheck]:
    """Run guardrail checks against a patch and attach results."""
    session = _get_session(session_id)
    patch = _find_patch(session, patch_id)
    try:
        from src.guardrails import check_patch as run_checks  # noqa: PLC0415

        results = run_checks(patch.diff, session.brand)
    except ImportError:
        logger.warning("src.guardrails not available — skipping checks")
        results = []
    patch.checks = results
    logger.info("Ran %d guardrail checks on patch %s", len(results), patch_id)
    return results


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: UUID) -> Session:
    """Return the full session including nested steps and patches."""
    return _get_session(session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session(session_id: UUID) -> Session:
    session = sessions.get(str(session_id))
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


def _get_step(session: Session, plan_step_id: str) -> PlanStep:
    for step in session.steps:
        if str(step.id) == plan_step_id:
            return step
    raise HTTPException(status_code=404, detail=f"PlanStep {plan_step_id} not found")


def _find_patch(session: Session, patch_id: UUID) -> PatchProposal:
    for step in session.steps:
        for patch in step.patches:
            if patch.id == patch_id:
                return patch
    raise HTTPException(status_code=404, detail=f"Patch {patch_id} not found")
