import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.models import Brand, PatchProposalInput, PlanStepInput

PLAN_TOOL = {
    "name": "output",
    "description": "Return implementation plan steps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "target_files": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["description", "target_files"],
                },
            }
        },
        "required": ["steps"],
    },
}

PATCH_TOOL = {
    "name": "output",
    "description": "Return a unified diff patch proposal.",
    "input_schema": {
        "type": "object",
        "properties": {"diff": {"type": "string"}},
        "required": ["diff"],
    },
}


def create_plan(title: str, description: str, brand: Brand) -> list[PlanStepInput]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _mock_plan()
    result = _call_tool(PLAN_TOOL, _plan_prompt(title, description, brand))
    return [PlanStepInput.model_validate(step) for step in result["steps"]]


def create_patch(step: PlanStepInput, brand: Brand) -> PatchProposalInput:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _mock_patch(step)
    result = _call_tool(PATCH_TOOL, _patch_prompt(step, brand))
    return PatchProposalInput.model_validate(result)


def _call_tool(tool: dict[str, Any], prompt: str) -> dict[str, Any]:
    client = Anthropic()
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=4096,
        tools=[tool],
        tool_choice={"type": "tool", "name": "output"},
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].input


def _read_agents(brand: Brand) -> str:
    path = Path(f"{brand}/AGENTS.md")
    return path.read_text() if path.exists() else ""


def _plan_prompt(title: str, description: str, brand: Brand) -> str:
    agents = _read_agents(brand)
    agents_section = f"Brand guidelines:\n{agents}\n" if agents else ""
    return (
        f"Create an implementation plan for a {brand} AI coding session.\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"{agents_section}"
        "Return only the output tool payload."
    )


def _patch_prompt(step: PlanStepInput, brand: Brand) -> str:
    agents = _read_agents(brand)
    agents_section = (
        f"\nBrand guardrail rules — your patch MUST comply:\n{agents}\n"
        if agents
        else ""
    )
    return (
        "Create a unified diff for this implementation step.\n"
        f"Description: {step.description}\n"
        f"Target files: {', '.join(step.target_files)}\n"
        f"{agents_section}"
        "Return only the output tool payload."
    )


def _mock_plan() -> list[PlanStepInput]:
    return [
        PlanStepInput(
            description="Implement deterministic guardrail evaluation",
            target_files=["src/guardrails.py", "tests/test_guardrails.py"],
        )
    ]


def _mock_patch(step: PlanStepInput) -> PatchProposalInput:
    target = step.target_files[0] if step.target_files else "pricing/discount.py"
    diff = (
        f"--- a/{target}\n"
        f"+++ b/{target}\n"
        "@@ -0,0 +1,5 @@\n"
        "+from .utils import calc\n"
        "+def apply_discount(order, pct):\n"
        '+    """Apply discount to order."""\n'
        '+    print(f"Discount applied: {pct}")\n'
        "+    requests.get(provider_url)\n"
    )
    return PatchProposalInput(diff=diff)
