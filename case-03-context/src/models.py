from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Brand = Literal["efood", "glovo", "talabat"]
ToolOutcome = Literal["success", "schema_invalid", "brand_denied", "tool_error"]


class ToolInvocation(BaseModel):
    tool_call_id: UUID
    caller_brand: Brand
    tool_name: str
    args: dict[str, object]
    outcome: ToolOutcome
    denial_reason: str | None = None
    result_summary: str | None = None
    latency_ms: int = Field(ge=0)
    called_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
