"""LLM integration with just-in-time AGENTS.md context injection."""
import logging
import os
from pathlib import Path
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


def _read_agents(brand: str) -> str:
    """Read AGENTS.md for the given brand at call time (just-in-time)."""
    return Path(f"{brand}/AGENTS.md").read_text()


def _call(brand: str, prompt: str, tool_schema: dict) -> Any:
    """Call Claude with tool_use to force valid structured JSON output."""
    agents_content = _read_agents(brand)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None  # caller handles mock

    system = (
        f"You are a code change planner for the {brand} brand. "
        f"Follow these Engineering Manifesto rules:\n\n{agents_content}"
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        tools=[{"name": "output", "description": "Return the result", "input_schema": tool_schema}],
        tool_choice={"type": "tool", "name": "output"},
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].input


def generate(prompt: str, brand: str, schema: type) -> dict:
    """Return a single schema-validated dict from the LLM."""
    result = _call(brand, prompt, schema.model_json_schema())
    if result is None:
        return _mock(schema)
    logger.debug("LLM response for %s: %s", schema.__name__, result)
    return result


def generate_list(prompt: str, brand: str, schema: type) -> list[dict]:
    """Return a list of schema-validated dicts from the LLM."""
    list_schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": schema.model_json_schema()}},
        "required": ["items"],
    }
    result = _call(brand, prompt, list_schema)
    if result is None:
        return [_mock(schema)]
    logger.debug("LLM list response for %s: %s", schema.__name__, result)
    return result["items"]


def _mock(schema: type) -> dict:
    """Deterministic fallback when ANTHROPIC_API_KEY is absent."""
    name = schema.__name__
    if name == "PlanStepInput":
        return {"description": "Add apply_discount function", "target_files": ["pricing/discount.py"]}
    if name == "PatchProposalInput":
        return {
            "diff": (
                "+from .utils import calc\n"
                "+def apply_discount(order, pct):\n"
                '+    print(f"Discount applied: {pct}")\n'
                "+    requests.get(provider_url)\n"
            ),
        }
    return {k: "" for k in schema.model_fields}
