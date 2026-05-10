import re
from collections.abc import Callable
from pathlib import Path

from src.models import Brand, GuardrailCheck

RuleMatcher = Callable[[list[str]], bool]

_FALLBACK_SEVERITY: dict[str, str] = {
    "R1": "WARN",
    "R2": "BLOCK",
    "R3": "WARN",
    "R4": "BLOCK",
    "R5": "BLOCK",
    "G1": "BLOCK",
    "G2": "BLOCK",
    "G3": "BLOCK",
    "G4": "WARN",
    "G5": "WARN",
}


def run_checks(diff: str, brand: Brand) -> list[GuardrailCheck]:
    added = _added_lines(diff)
    sev = _parse_severities(brand)
    if brand == "glovo":
        return [
            _check(
                "G1",
                sev.get("G1", "BLOCK"),
                _has_float_money,
                added,
                "float() call detected — money arithmetic must use Decimal",
            ),
            _check(
                "G2",
                sev.get("G2", "BLOCK"),
                _has_hardcoded_url,
                added,
                "hardcoded URL literal detected — must use glovo.config",
            ),
            _check(
                "G3",
                sev.get("G3", "BLOCK"),
                _has_direct_engine_connect,
                added,
                "direct engine.connect() detected — must use glovo.db.session context manager",
            ),
            _check(
                "G4",
                sev.get("G4", "WARN"),
                _missing_glovo_trace_id,
                added,
                "public handler missing X-Glovo-Trace-Id propagation",
            ),
            _check(
                "G5",
                sev.get("G5", "WARN"),
                _has_public_function_without_args_docstring,
                added,
                "public function missing docstring with Args: line",
            ),
        ]
    return [
        _check(
            "R1",
            sev.get("R1", "WARN"),
            _has_relative_import,
            added,
            "relative import detected",
        ),
        _check(
            "R2",
            sev.get("R2", "BLOCK"),
            _has_shell_execution,
            added,
            "shell execution call detected (os.system or subprocess)",
        ),
        _check(
            "R3",
            sev.get("R3", "WARN"),
            _has_public_function_without_docstring,
            added,
            "public function missing docstring",
        ),
        _check(
            "R4",
            sev.get("R4", "BLOCK"),
            _has_print_call,
            added,
            "print() call detected — use structured logging",
        ),
        _check(
            "R5",
            sev.get("R5", "BLOCK"),
            _has_requests_call,
            added,
            "requests.* HTTP call detected — use approved async client",
        ),
    ]


def _parse_severities(brand: Brand) -> dict[str, str]:
    try:
        text = Path(f"{brand}/AGENTS.md").read_text()
    except FileNotFoundError:
        return _FALLBACK_SEVERITY.copy()
    pattern = re.compile(r"-\s+([A-Z]\d+)\s+(WARN|BLOCK|INFO):")
    parsed = {m.group(1): m.group(2) for m in pattern.finditer(text)}
    return {**_FALLBACK_SEVERITY, **parsed}


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
    description: str,
) -> GuardrailCheck:
    violated = matcher(added)
    result = "fail" if violated else "pass"
    reason = (
        f"{description} — per AGENTS.md {rule_id}"
        if violated
        else f"no violation — per AGENTS.md {rule_id}"
    )
    return GuardrailCheck(
        ruleId=rule_id,
        severity=severity,
        result=result,
        reason=reason,
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
    return re.search(r"^\s*(?:async\s+)?def\s+(?!_)[A-Za-z_]\w*\s*\(", line) is not None


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


def _has_float_money(added: list[str]) -> bool:
    return any(re.search(r"\bfloat\s*\(", line) for line in added)


def _has_hardcoded_url(added: list[str]) -> bool:
    return any(re.search(r"""["']https?://""", line) for line in added)


def _has_direct_engine_connect(added: list[str]) -> bool:
    return any(re.search(r"\bengine\.connect\s*\(", line) for line in added)


def _missing_glovo_trace_id(added: list[str]) -> bool:
    has_public_handler = any(_is_public_function(line) for line in added)
    has_trace_context = any(
        "X-Glovo-Trace-Id" in line or "trace_id" in line for line in added
    )
    return has_public_handler and not has_trace_context


def _has_public_function_without_args_docstring(added: list[str]) -> bool:
    for index, line in enumerate(added):
        if _is_public_function(line) and not _next_docstring_has_args(added, index):
            return True
    return False


def _next_docstring_has_args(added: list[str], index: int) -> bool:
    for line in added[index + 1 :]:
        stripped = line.strip()
        if not stripped:
            continue
        return stripped.startswith(('"""', "'''")) and "Args:" in "\n".join(
            added[index + 1 : index + 6]
        )
    return False
