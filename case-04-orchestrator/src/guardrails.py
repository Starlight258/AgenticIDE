"""Deterministic regex guardrails for generated diffs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel

try:
    from src.models import GuardrailCheck
except ModuleNotFoundError as exc:
    if exc.name != "src.models":
        raise

    class GuardrailCheck(BaseModel):
        """Fallback until the routes/models branch is merged."""

        ruleId: str
        severity: Literal["BLOCK", "WARN", "INFO"]
        result: Literal["pass", "fail"]
        reason: str


Brand = Literal["efood", "glovo", "talabat"] | str
Severity = Literal["BLOCK", "WARN", "INFO"]

DEFAULT_SEVERITIES: dict[str, Severity] = {
    "R1": "WARN",
    "R2": "BLOCK",
    "R3": "WARN",
    "R4": "BLOCK",
    "R5": "BLOCK",
}

RULE_PATTERN = re.compile(r"\b(R[1-5])\b\s*(?:[-:])?\s*\b(BLOCK|WARN|INFO)\b")
REQUESTS_PATTERN = re.compile(r"\brequests\.(get|post|put|delete|patch)\s*\(")


def run_checks(diff: str, brand: Brand) -> list[GuardrailCheck]:
    """Evaluate a unified diff against AGENTS.md-backed rules."""
    severities = _parse_severities(brand)
    lines = _added_lines(diff)
    failures = {
        "R1": _check_r1(lines),
        "R2": _check_r2(lines),
        "R3": _check_r3(lines),
        "R4": _check_r4(lines),
        "R5": _check_r5(lines),
    }
    return [
        _build_check(rule_id, severities[rule_id], failures[rule_id])
        for rule_id in DEFAULT_SEVERITIES
    ]


def _parse_severities(brand: Brand) -> dict[str, Severity]:
    """Read brand-specific AGENTS.md first, then root AGENTS.md."""
    path = _agents_path(brand)
    if path is None:
        return DEFAULT_SEVERITIES.copy()
    severities = DEFAULT_SEVERITIES.copy()
    severities.update(_extract_severities(path.read_text()))
    return severities


def _agents_path(brand: Brand) -> Path | None:
    root = Path.cwd()
    brand_path = root / str(brand) / "AGENTS.md"
    if brand_path.exists():
        return brand_path
    root_path = root / "AGENTS.md"
    if root_path.exists():
        return root_path
    return None


def _extract_severities(text: str) -> dict[str, Severity]:
    return {
        match.group(1): cast(Severity, match.group(2))
        for match in RULE_PATTERN.finditer(text)
    }


def _added_lines(diff: str) -> list[str]:
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _build_check(
    rule_id: str,
    severity: Severity,
    failure_reason: str | None,
) -> GuardrailCheck:
    result = "fail" if failure_reason else "pass"
    reason = failure_reason or f"No violation detected per AGENTS.md {rule_id}"
    return GuardrailCheck(
        ruleId=rule_id,
        severity=severity,
        result=result,
        reason=reason,
    )


def _check_r1(lines: list[str]) -> str | None:
    for line in lines:
        if re.search(r"\bfrom\s+\.", line):
            return (
                f"Relative import detected: '{line.strip()}' - use absolute imports "
                "per AGENTS.md R1"
            )
    return None


def _check_r2(lines: list[str]) -> str | None:
    for line in lines:
        match = re.search(r"\b(?:os\.system\s*\(|subprocess\.)", line)
        if match:
            return (
                f"Unsafe shell call '{match.group(0)}' - requires explicit security "
                "review per AGENTS.md R2"
            )
    return None


def _check_r3(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if _is_public_function(line) and not _has_following_docstring(lines, index):
            return "Public function missing docstring per AGENTS.md R3"
    return None


def _is_public_function(line: str) -> bool:
    return bool(re.match(r"\s*def\s+[a-z][A-Za-z0-9]*\s*\(", line))


def _has_following_docstring(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    return '"""' in lines[index + 1] or "'''" in lines[index + 1]


def _check_r4(lines: list[str]) -> str | None:
    for line in lines:
        if re.search(r"\bprint\s*\(", line):
            return "print() call detected - use efood.logging per AGENTS.md R4"
    return None


def _check_r5(lines: list[str]) -> str | None:
    for line in lines:
        match = REQUESTS_PATTERN.search(line)
        if match:
            method = match.group(1)
            return (
                f"Direct requests.{method} call - use efood.http_client "
                "per AGENTS.md R5"
            )
    return None
