from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


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
