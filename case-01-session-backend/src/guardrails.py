import re
from src.models import GuardrailCheck


def check_patch(patch_text: str, brand: str) -> list[GuardrailCheck]:
    """Evaluate a unified diff against the brand's AGENTS.md rules.

    Returns one GuardrailCheck per rule regardless of pass/fail.
    brand is present for future multi-brand AGENTS.md routing.
    """
    added_lines = [
        line[1:]
        for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]
    return [
        _check_r1(added_lines),
        _check_r2(added_lines),
        _check_r3(added_lines),
        _check_r4(added_lines),
        _check_r5(added_lines),
    ]


def _check_r1(lines: list[str]) -> GuardrailCheck:
    """R1 — Absolute imports only (WARN)."""
    for line in lines:
        if re.search(r"from\s+\.", line):
            return GuardrailCheck(
                ruleId="R1",
                severity="WARN",
                result="fail",
                reason="Relative import detected — use absolute imports per AGENTS.md R1",
            )
    return GuardrailCheck(
        ruleId="R1",
        severity="WARN",
        result="pass",
        reason="All imports are absolute per AGENTS.md R1",
    )


def _check_r2(lines: list[str]) -> GuardrailCheck:
    """R2 — No os.system / subprocess (BLOCK)."""
    for line in lines:
        if re.search(r"os\.system\(|subprocess\.", line):
            return GuardrailCheck(
                ruleId="R2",
                severity="BLOCK",
                result="fail",
                reason="Unsafe shell call detected — requires security review per AGENTS.md R2",
            )
    return GuardrailCheck(
        ruleId="R2",
        severity="BLOCK",
        result="pass",
        reason="No unsafe shell calls per AGENTS.md R2",
    )


def _check_r3(lines: list[str]) -> GuardrailCheck:
    """R3 — Public functions have docstrings (WARN)."""
    for i, line in enumerate(lines):
        if re.match(r"def [a-zA-Z][^_]", line):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if '"""' not in next_line:
                return GuardrailCheck(
                    ruleId="R3",
                    severity="WARN",
                    result="fail",
                    reason="Public function missing docstring per AGENTS.md R3",
                )
    return GuardrailCheck(
        ruleId="R3",
        severity="WARN",
        result="pass",
        reason="Public functions have docstrings per AGENTS.md R3",
    )


def _check_r4(lines: list[str]) -> GuardrailCheck:
    """R4 — No print() (BLOCK)."""
    for line in lines:
        if re.search(r"\bprint\s*\(", line):
            return GuardrailCheck(
                ruleId="R4",
                severity="BLOCK",
                result="fail",
                reason="print() call detected — use efood.logging per AGENTS.md R4",
            )
    return GuardrailCheck(
        ruleId="R4",
        severity="BLOCK",
        result="pass",
        reason="No print() calls — logging used correctly per AGENTS.md R4",
    )


def _check_r5(lines: list[str]) -> GuardrailCheck:
    """R5 — No direct requests (BLOCK)."""
    for line in lines:
        if re.search(r"\brequests\.(get|post|put|delete|patch|head|options)\b", line):
            return GuardrailCheck(
                ruleId="R5",
                severity="BLOCK",
                result="fail",
                reason="Direct requests call detected — use efood.http_client per AGENTS.md R5",
            )
    return GuardrailCheck(
        ruleId="R5",
        severity="BLOCK",
        result="pass",
        reason="No direct HTTP calls — efood.http_client used per AGENTS.md R5",
    )
