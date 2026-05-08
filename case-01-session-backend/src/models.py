from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


class PlanStepInput(BaseModel):
    """LLM-facing schema for plan step generation — no nested children."""
    description: str
    target_files: list[str]


class PatchProposalInput(BaseModel):
    """LLM-facing schema for patch generation — diff only."""
    diff: str


class PlanStepOut(BaseModel):
    """Response schema for POST /plan — no patches, signals SRP."""
    id: UUID
    description: str
    target_files: list[str]


class PatchProposalOut(BaseModel):
    """Response schema for POST /patches — no checks, signals SRP."""
    id: UUID
    planStepId: UUID
    diff: str
    created_at: datetime


class GuardrailCheck(BaseModel):
    ruleId: str
    severity: Severity
    result: CheckResult
    reason: str


class PatchProposal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    planStepId: UUID
    diff: str
    checks: list[GuardrailCheck] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    description: str
    target_files: list[str]
    patches: list[PatchProposal] = []


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    brand: Brand
    trace_id: UUID = Field(default_factory=uuid4)
    steps: list[PlanStep] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
