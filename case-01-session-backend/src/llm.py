"""LLM integration with just-in-time AGENTS.md context injection."""
import json
import logging
import os
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)


def _read_agents(brand: str) -> str:
    """Read AGENTS.md for the given brand at call time (just-in-time)."""
    return Path(f"{brand}/AGENTS.md").read_text()


def _build_system_prompt(brand: str, agents_content: str, schema: type) -> str:
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    return (
        f"You are a code change planner for the {brand} brand. "
        f"Follow these Engineering Manifesto rules:\n\n{agents_content}\n\n"
        f"Respond ONLY with valid JSON matching this schema:\n{schema_json}"
    )


def _mock_for_schema(schema: type) -> dict:
    """Return a deterministic mock dict when no API key is configured."""
    name = schema.__name__
    if name == "PlanStep":
        return {"description": "Mock plan step", "target_files": ["pricing/discount.py"]}
    if name == "PatchProposal":
        return {
            "planStepId": "<planStepId>",
            "diff": (
                "+from .utils import calc\n"
                "+def apply_discount(order, pct):\n"
                '+    print(f"Discount applied: {pct}")\n'
                "+    requests.get(provider_url)\n"
            ),
        }
    # Generic fallback: fill each field with a sensible empty value
    return {k: "" for k in schema.model_fields}


def generate(prompt: str, brand: str, schema: type) -> dict:
    """Call the LLM with AGENTS.md injected as system context and return a dict."""
    agents_content = _read_agents(brand)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — returning mock response for %s", schema.__name__)
        return _mock_for_schema(schema)

    system_prompt = _build_system_prompt(brand, agents_content, schema)
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    logger.debug("LLM raw response: %s", raw)
    return json.loads(raw)


def generate_list(prompt: str, brand: str, schema: type) -> list[dict]:
    """Call the LLM expecting a JSON array of schema objects."""
    agents_content = _read_agents(brand)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.info(
            "ANTHROPIC_API_KEY not set — returning mock list response for %s", schema.__name__
        )
        return [_mock_for_schema(schema)]

    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    system_prompt = (
        f"You are a code change planner for the {brand} brand. "
        f"Follow these Engineering Manifesto rules:\n\n{agents_content}\n\n"
        f"Respond ONLY with a valid JSON array where each element matches this schema:\n{schema_json}"
    )
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    logger.debug("LLM raw list response: %s", raw)
    return json.loads(raw)
