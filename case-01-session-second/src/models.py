from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


class SessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    brand: Brand


class PatchCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: UUID


class PlanStepInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    target_files: list[str]


class PatchProposalInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    diff: str


class PlanStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    description: str
    target_files: list[str]


class PatchProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    step_id: UUID
    diff: str
    created_at: datetime


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
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime
