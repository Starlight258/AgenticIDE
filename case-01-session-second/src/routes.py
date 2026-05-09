from uuid import UUID

from fastapi import APIRouter, HTTPException

from src import service
from src.models import (
    GuardrailCheck,
    PatchCreate,
    PatchProposalOut,
    PlanStepOut,
    Session,
    SessionCreate,
)

router = APIRouter()


@router.post("/sessions", response_model=Session)
def create_session(payload: SessionCreate) -> Session:
    created = service.create_session(payload)
    return Session.model_validate(created)


@router.post("/sessions/{session_id}/plan", response_model=list[PlanStepOut])
def create_plan(session_id: UUID) -> list[PlanStepOut]:
    try:
        return service.create_plan(session_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/patches", response_model=PatchProposalOut)
def create_patch(session_id: UUID, payload: PatchCreate) -> PatchProposalOut:
    try:
        return service.create_patch(session_id, payload)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/patches/{patch_id}/check",
    response_model=list[GuardrailCheck],
)
def check_patch_in_session(session_id: UUID, patch_id: UUID) -> list[GuardrailCheck]:
    try:
        return service.check_patch_in_session(session_id, patch_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/patches/{patch_id}/check", response_model=list[GuardrailCheck])
def check_patch(patch_id: UUID) -> list[GuardrailCheck]:
    try:
        return service.check_patch(patch_id)
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: UUID) -> Session:
    try:
        return Session.model_validate(service.get_session(session_id))
    except service.NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
