"""Pydantic models for tool contracts and audit records."""

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Outcome = Literal["success", "schema_invalid", "brand_denied", "tool_error"]
ToolOutcome = Outcome


class SearchPrsArgs(BaseModel):
    """Arguments for searching pull requests."""

    model_config = ConfigDict(extra="forbid")

    brand: Brand
    query: str = Field(min_length=1)
    limit: int = Field(ge=1, le=50)


class GetSlackMessagesArgs(BaseModel):
    """Arguments for reading Slack messages from one channel."""

    model_config = ConfigDict(extra="forbid")

    brand: Brand
    channel: str = Field(min_length=1)
    since: datetime


class FetchGdriveDocArgs(BaseModel):
    """Arguments for fetching a Google Drive document."""

    model_config = ConfigDict(extra="forbid")

    brand: Brand
    doc_id: str = Field(min_length=1)


class ToolDefinition(BaseModel):
    """Catalog entry returned by GET /tools."""

    name: str
    description: str
    args_schema: dict[str, Any]
    brand_requirements: str


class ToolInvokeResponse(BaseModel):
    """Response returned after a tool invocation."""

    tool_call_id: UUID
    result: Any


class ToolInvocation(BaseModel):
    """Stored audit event for every accepted invocation attempt."""

    tool_call_id: UUID
    caller_brand: Brand
    tool_name: str
    args: dict[str, Any]
    outcome: Outcome
    denial_reason: str | None = None
    result_summary: str | None = None
    latency_ms: int = Field(ge=0)
    called_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditRecord(ToolInvocation):
    """External audit record shape."""
