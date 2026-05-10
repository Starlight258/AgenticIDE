"""Pydantic models for tool contracts and audit records."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Outcome = Literal["success", "schema_invalid", "brand_denied", "tool_error"]


class SearchPrsArgs(BaseModel):
    """Arguments for searching pull requests."""

    model_config = ConfigDict(extra="forbid")

    brand: Brand
    query: str = Field(min_length=1)


class GetSlackMessagesArgs(BaseModel):
    """Arguments for reading Slack messages from one channel."""

    model_config = ConfigDict(extra="forbid")

    brand: Brand
    channel_id: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


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


class ToolInvokeResponse(BaseModel):
    """Response returned after a tool invocation."""

    tool_call_id: UUID
    result: dict[str, Any]


class ToolInvocation(BaseModel):
    """Stored audit event for every accepted invocation attempt."""

    tool_call_id: UUID
    caller_brand: Brand
    tool_name: str
    args: dict[str, Any]
    outcome: Outcome
    denial_reason: str | None = None
    result_summary: str | None = None
    latency_ms: int
    called_at: datetime


class AuditRecord(ToolInvocation):
    """External audit record shape."""
