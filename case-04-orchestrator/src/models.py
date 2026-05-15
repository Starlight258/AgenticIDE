"""Domain models for the orchestrator workflow."""

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Brand = Literal["efood", "glovo", "talabat"]
JobStatus = Literal["pending", "dispatched", "done", "partial_failure"]
TaskStatus = Literal["queued", "running", "ready", "blocked", "failed"]
CheckSeverity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class GuardrailCheck(BaseModel):
    ruleId: str
    severity: CheckSeverity
    result: CheckResult
    reason: str


class AgentResult(BaseModel):
    diff: str
    files: list[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str = Field(default_factory=new_id)
    issue: str
    status: TaskStatus = "queued"
    worktree_path: str | None = None
    branch: str | None = None
    diff: str | None = None
    checks: list[GuardrailCheck] = Field(default_factory=list)
    result: AgentResult | None = None
    pr_url: str | None = None


class Job(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    status: JobStatus = "pending"
    brand: Brand
    repo_path: str
    trace_id: str = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=utc_now)
    tasks: list[Task] = Field(default_factory=list)
