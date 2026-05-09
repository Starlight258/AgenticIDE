"""DTOs — request, response, and LLM I/O schemas.

Separate from domain models: these cross layer boundaries and change when
API contracts or LLM prompts change, not when business rules change.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.models import Brand


# ── Request DTOs ──────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    brand: Brand


class PatchCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: UUID


# ── LLM I/O DTOs ─────────────────────────────────────────────────────────────

class PlanStepInput(BaseModel):
    """What the LLM produces for one plan step. No id, no child lists."""

    model_config = ConfigDict(from_attributes=True)

    description: str
    target_files: list[str]


class PatchProposalInput(BaseModel):
    """What the LLM produces for one patch. Diff string only."""

    model_config = ConfigDict(from_attributes=True)

    diff: str


# ── Response DTOs ─────────────────────────────────────────────────────────────

class PlanStepOut(BaseModel):
    """POST /plan response — no patches (response shape = workflow signal)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    target_files: list[str]


class PatchProposalOut(BaseModel):
    """POST /patches response — no checks (SRP: patch ≠ check)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    diff: str
    created_at: datetime
