import json
from datetime import UTC, datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class SessionRow(SQLModel, table=True):
    __tablename__ = "sessions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    description: str
    brand: str
    trace_id: UUID = Field(default_factory=uuid4)
    owner_id: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlanStepRow(SQLModel, table=True):
    __tablename__ = "plan_steps"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(foreign_key="sessions.id")
    description: str
    target_files: str = Field(default="[]")  # JSON-encoded list[str]

    def get_target_files(self) -> list[str]:
        return json.loads(self.target_files)

    def set_target_files(self, files: list[str]) -> None:
        self.target_files = json.dumps(files)


class PatchProposalRow(SQLModel, table=True):
    __tablename__ = "patch_proposals"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    step_id: UUID = Field(foreign_key="plan_steps.id")
    brand: str
    diff: str
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GuardrailCheckRow(SQLModel, table=True):
    __tablename__ = "guardrail_checks"

    id: Optional[int] = Field(default=None, primary_key=True)
    patch_id: UUID = Field(foreign_key="patch_proposals.id")
    rule_id: str
    severity: str
    result: str
    reason: str


class AuditEventRow(SQLModel, table=True):
    __tablename__ = "audit_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    trace_id: UUID
    actor: str
    action: str
    resource_type: str
    resource_id: UUID
    prompt: Optional[str] = Field(default=None)
    response: Optional[str] = Field(default=None)
    tokens_input: int = Field(default=0)
    tokens_output: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdempotencyRecord(SQLModel, table=True):
    __tablename__ = "idempotency_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    response_json: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
