"""HTTP request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models import Brand, CheckSeverity, CheckResult, JobStatus, TaskStatus


class JobCreate(BaseModel):
    title: str
    issues: list[str] = Field(min_length=1)
    repo_path: str
    brand: Brand


class GuardrailCheckOut(BaseModel):
    ruleId: str
    severity: CheckSeverity
    result: CheckResult
    reason: str


class TaskOut(BaseModel):
    id: str
    issue: str
    status: TaskStatus
    worktree_path: str | None
    diff: str | None
    checks: list[GuardrailCheckOut]


class JobOut(BaseModel):
    id: str
    title: str
    status: JobStatus
    brand: Brand
    trace_id: str
    created_at: datetime
    tasks: list[TaskOut]


class JobCreatedOut(BaseModel):
    id: str
    title: str
    status: JobStatus
    brand: Brand
    trace_id: str
    created_at: datetime


class DispatchOut(BaseModel):
    job_id: str
    task_count: int
    tasks: list[TaskOut]


class PROut(BaseModel):
    pr_url: str
    branch: str
    worktree_path: str | None
