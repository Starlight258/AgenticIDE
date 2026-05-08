import re
from collections.abc import Callable

from src.models import GuardrailCheck

RuleMatcher = Callable[[list[str]], bool]


def run_checks(diff: str) -> list[GuardrailCheck]:
    added = _added_lines(diff)
    return [
        _check("R1", "WARN", _has_relative_import, added),
        _check("R2", "BLOCK", _has_shell_execution, added),
        _check("R3", "WARN", _has_public_function_without_docstring, added),
        _check("R4", "BLOCK", _has_print_call, added),
        _check("R5", "BLOCK", _has_requests_call, added),
    ]


def _added_lines(diff: str) -> list[str]:
    return [
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _check(
    rule_id: str,
    severity: str,
    matcher: RuleMatcher,
    added: list[str],
) -> GuardrailCheck:
    result = "fail" if matcher(added) else "pass"
    return GuardrailCheck(
        ruleId=rule_id,
        severity=severity,
        result=result,
        reason=f"per AGENTS.md {rule_id}",
    )


def _has_relative_import(added: list[str]) -> bool:
    return any(re.search(r"^\s*from\s+\.", line) for line in added)


def _has_shell_execution(added: list[str]) -> bool:
    pattern = re.compile(r"\b(os\.system|subprocess(?:\.|\b))")
    return any(pattern.search(line) for line in added)


def _has_public_function_without_docstring(added: list[str]) -> bool:
    for index, line in enumerate(added):
        has_missing_docstring = not _next_added_line_is_docstring(added, index)
        if _is_public_function(line) and has_missing_docstring:
            return True
    return False


def _is_public_function(line: str) -> bool:
    return re.search(r"^\s*def\s+(?!_)[A-Za-z_]\w*\s*\(", line) is not None


def _next_added_line_is_docstring(added: list[str], index: int) -> bool:
    for line in added[index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith(('"""', "'''"))
    return False


def _has_print_call(added: list[str]) -> bool:
    return any(re.search(r"(^|[^\w.])print\s*\(", line) for line in added)


def _has_requests_call(added: list[str]) -> bool:
    pattern = re.compile(r"\brequests\.(get|post|put|patch|delete|head|options)\s*\(")
    return any(pattern.search(line) for line in added)
