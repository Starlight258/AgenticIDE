"""HTTP routes for catalog, invoke, and audit."""

from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, get_args
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, ValidationError

from src.models import (
    FetchGdriveDocArgs,
    GetSlackMessagesArgs,
    Outcome,
    SearchPrsArgs,
    Brand,
    ToolDefinition,
    ToolInvocation,
    ToolInvokeResponse,
)
from src.permissions import (
    PermissionDecision,
    check_fetch_gdrive_doc,
    check_get_slack_messages,
    check_search_prs,
)
from src.store import add_invocation
from src.tools import fetch_gdrive_doc, get_slack_messages, list_tools, search_prs

router = APIRouter()
BRANDS = set(get_args(Brand))


class ToolSpec(BaseModel):
    """Internal registry entry for one invokable tool."""

    args_model: type[BaseModel]
    permission: Callable[[Brand, Any], PermissionDecision]
    execute: Callable[[Any], tuple[dict[str, Any], str]]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_prs": ToolSpec(
        args_model=SearchPrsArgs,
        permission=check_search_prs,
        execute=search_prs,
    ),
    "get_slack_messages": ToolSpec(
        args_model=GetSlackMessagesArgs,
        permission=check_get_slack_messages,
        execute=get_slack_messages,
    ),
    "fetch_gdrive_doc": ToolSpec(
        args_model=FetchGdriveDocArgs,
        permission=check_fetch_gdrive_doc,
        execute=fetch_gdrive_doc,
    ),
}


@router.get("/tools")
def get_tools() -> list[ToolDefinition]:
    """Return the tool catalog."""
    return list_tools()


@router.post("/tools/{name}/invoke")
def invoke_tool(
    name: str,
    payload: dict[str, Any] = Body(...),
    x_caller_brand: str = Header(alias="X-Caller-Brand"),
) -> ToolInvokeResponse:
    """Validate, authorize, execute, and audit one tool call."""
    started_at = perf_counter()
    tool_call_id = uuid4()
    caller_brand = parse_caller_brand(x_caller_brand)
    spec = get_tool_spec(name)
    args = validate_args(spec, payload, tool_call_id, caller_brand, name, started_at)
    decision = spec.permission(caller_brand, args)
    if not decision.allowed:
        audit(
            tool_call_id,
            caller_brand,
            name,
            payload,
            "brand_denied",
            started_at,
            decision.denial_reason,
        )
        raise HTTPException(status_code=403, detail=decision.denial_reason)
    result, summary = spec.execute(args)
    audit(
        tool_call_id, caller_brand, name, payload, "success", started_at, None, summary
    )
    return ToolInvokeResponse(tool_call_id=tool_call_id, result=result)


def parse_caller_brand(raw_brand: str) -> Brand:
    """Parse X-Caller-Brand into a supported brand."""
    if raw_brand in BRANDS:
        return raw_brand  # type: ignore[return-value]
    raise HTTPException(status_code=400, detail="invalid X-Caller-Brand")


def get_tool_spec(name: str) -> ToolSpec:
    """Find a tool registry entry or raise a 404."""
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        raise HTTPException(status_code=404, detail="unknown tool")
    return spec


def validate_args(
    spec: ToolSpec,
    payload: dict[str, Any],
    tool_call_id: UUID,
    caller_brand: Brand,
    tool_name: str,
    started_at: float,
) -> BaseModel:
    """Validate raw args and audit schema failures."""
    try:
        return spec.args_model.model_validate(payload)
    except ValidationError as exc:
        audit(
            tool_call_id,
            caller_brand,
            tool_name,
            payload,
            "schema_invalid",
            started_at,
            str(exc),
        )
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def audit(
    tool_call_id: UUID,
    caller_brand: Brand,
    tool_name: str,
    args: dict[str, Any],
    outcome: Outcome,
    started_at: float,
    denial_reason: str | None = None,
    result_summary: str | None = None,
) -> None:
    """Store a completed invocation audit event."""
    add_invocation(
        ToolInvocation(
            tool_call_id=tool_call_id,
            caller_brand=caller_brand,
            tool_name=tool_name,
            args=args,
            outcome=outcome,
            denial_reason=denial_reason,
            result_summary=result_summary,
            latency_ms=elapsed_ms(started_at),
            called_at=datetime.now(UTC),
        )
    )


def elapsed_ms(started_at: float) -> int:
    """Return elapsed milliseconds for a monotonic start time."""
    return int((perf_counter() - started_at) * 1000)
