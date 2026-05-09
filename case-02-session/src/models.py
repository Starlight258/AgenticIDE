"""Domain models — business concepts, not transport shapes."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


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
    checks: list[GuardrailCheck] = Field(default_factory=list)
    created_at: datetime


class PlanStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    target_files: list[str]
    patches: list[PatchProposal] = Field(default_factory=list)


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    brand: Brand
    trace_id: UUID
    owner_id: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime
