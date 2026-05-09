from pathlib import Path
from typing import Any, Protocol

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Settings
from src.logging_config import get_logger
from src.models import Brand
from src.schemas import PatchProposalInput, PlanStepInput

logger = get_logger(__name__)

_PLAN_TOOL_SCHEMA = {
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

_PATCH_TOOL_SCHEMA = {
    "name": "output",
    "description": "Return a unified diff patch proposal.",
    "input_schema": {
        "type": "object",
        "properties": {"diff": {"type": "string"}},
        "required": ["diff"],
    },
}


class LLMUnavailableError(Exception):
    """Raised when the LLM service is unavailable after retries."""


class LLMProvider(Protocol):
    async def create_plan(
        self,
        title: str,
        description: str,
        brand: Brand,
    ) -> list[PlanStepInput]: ...

    async def create_patch(
        self,
        step: PlanStepInput,
        brand: Brand,
    ) -> PatchProposalInput: ...


class AnthropicLLM:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_plan(
        self,
        title: str,
        description: str,
        brand: Brand,
    ) -> list[PlanStepInput]:
        if not self._settings.anthropic_api_key:
            logger.info("llm.mock_plan", title=title, brand=brand)
            return _mock_plan()

        prompt = _plan_prompt(title, description, brand)
        try:
            result, _ = await self._call_tool_with_retry(_PLAN_TOOL_SCHEMA, prompt)
        except anthropic.APIError as exc:
            raise LLMUnavailableError("LLM unavailable") from exc

        logger.info("llm.plan_created", brand=brand, steps=len(result.get("steps", [])))
        return [PlanStepInput.model_validate(step) for step in result["steps"]]

    async def create_patch(
        self,
        step: PlanStepInput,
        brand: Brand,
    ) -> PatchProposalInput:
        if not self._settings.anthropic_api_key:
            logger.info("llm.mock_patch", brand=brand)
            return _mock_patch(step)

        prompt = _patch_prompt(step, brand)
        try:
            result, _ = await self._call_tool_with_retry(_PATCH_TOOL_SCHEMA, prompt)
        except anthropic.APIError as exc:
            raise LLMUnavailableError("LLM unavailable") from exc

        logger.info("llm.patch_created", brand=brand)
        return PatchProposalInput.model_validate(result)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type(anthropic.APIStatusError),
        reraise=True,
    )
    async def _call_tool_with_retry(
        self,
        tool: dict[str, Any],
        prompt: str,
    ) -> tuple[dict[str, Any], dict[str, int]]:
        client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        response = await client.messages.create(
            model=self._settings.model,
            max_tokens=4096,
            tools=[tool],
            tool_choice={"type": "tool", "name": "output"},
            messages=[{"role": "user", "content": prompt}],
        )
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.content[0].input, usage


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
            description="Add payment charge handler",
            target_files=["payments/charge.py"],
        )
    ]


def _mock_patch(step: PlanStepInput) -> PatchProposalInput:
    sample_path = Path("glovo/sample_diff.patch")
    if sample_path.exists():
        return PatchProposalInput(diff=sample_path.read_text())
    target = step.target_files[0] if step.target_files else "payments/charge.py"
    return PatchProposalInput(diff=f"--- a/{target}\n+++ b/{target}\n")
