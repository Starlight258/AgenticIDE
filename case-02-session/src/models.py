"""Domain models — business concepts, not transport shapes."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]
ReadinessVerdict = Literal["READY", "NOT_READY"]


class GuardrailCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ruleId: str
    severity: Severity
    result: CheckResult
    reason: str


class PatchProposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    brand: Brand
    diff: str
    version: int = 0  # optimistic lock; incremented on each update
    checks: list[GuardrailCheck] = Field(default_factory=list)
    created_at: datetime


class PlanStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    target_files: list[str]
    patches: list[PatchProposal] = Field(default_factory=list)


class TestRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    patch_ids: list[UUID]
    outcome: Literal["PASS", "FAIL", "PARTIAL"]
    notes: str = ""
    created_at: datetime


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    brand: Brand
    trace_id: UUID
    owner_id: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    test_runs: list[TestRun] = Field(default_factory=list)
    created_at: datetime
