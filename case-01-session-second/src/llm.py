import os
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


def create_patch(step: PlanStepInput) -> PatchProposalInput:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _mock_patch(step)
    result = _call_tool(PATCH_TOOL, _patch_prompt(step))
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


def _plan_prompt(title: str, description: str, brand: Brand) -> str:
    return (
        f"Create an implementation plan for a {brand} AI coding session.\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        "Return only the output tool payload."
    )


def _patch_prompt(step: PlanStepInput) -> str:
    return (
        "Create a unified diff for this implementation step.\n"
        f"Description: {step.description}\n"
        f"Target files: {', '.join(step.target_files)}\n"
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
    target = step.target_files[0] if step.target_files else "src/example.py"
    diff = f"--- a/{target}\n+++ b/{target}\n@@\n+def generated_change():\n+    pass"
    return PatchProposalInput(diff=diff)
