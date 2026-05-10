from pathlib import Path

from src.guardrails import run_checks


def test_empty_patch_passes_all_rules() -> None:
    checks = run_checks("", "efood")

    assert len(checks) == 5
    assert {check.ruleId for check in checks} == {"R1", "R2", "R3", "R4", "R5"}
    assert all(check.result == "pass" for check in checks)


def test_r1_warns_on_relative_import() -> None:
    checks = run_checks("+from .models import Session", "efood")

    assert _result(checks, "R1") == "fail"
    assert _severity(checks, "R1") == "WARN"


def test_r2_blocks_os_system() -> None:
    checks = run_checks("+os.system(command)", "efood")

    assert _result(checks, "R2") == "fail"
    assert _severity(checks, "R2") == "BLOCK"


def test_r2_blocks_subprocess_import_or_usage() -> None:
    checks = run_checks("+import subprocess\n+subprocess.run(command)", "efood")

    assert _result(checks, "R2") == "fail"
    assert _severity(checks, "R2") == "BLOCK"


def test_r3_warns_on_public_function_without_docstring() -> None:
    checks = run_checks("+def create_item():\n+    return None", "efood")

    assert _result(checks, "R3") == "fail"
    assert _severity(checks, "R3") == "WARN"


def test_r3_passes_public_function_with_docstring() -> None:
    diff = '+def create_item():\n+    """Create an item."""\n+    return None'
    checks = run_checks(diff, "efood")

    assert _result(checks, "R3") == "pass"


def test_r4_blocks_print_call() -> None:
    checks = run_checks("+print(value)", "efood")

    assert _result(checks, "R4") == "fail"
    assert _severity(checks, "R4") == "BLOCK"


def test_r5_blocks_requests_call() -> None:
    checks = run_checks("+requests.post(url, json=payload)", "efood")

    assert _result(checks, "R5") == "fail"
    assert _severity(checks, "R5") == "BLOCK"


def test_only_added_lines_are_checked() -> None:
    diff = "--- a/app.py\n+++ b/app.py\n-print(secret)\n context\n+value = 1"

    checks = run_checks(diff, "efood")

    assert all(check.result == "pass" for check in checks)


def test_glovo_sample_diff_all_five_fail() -> None:
    diff = Path("glovo/sample_diff.patch").read_text()
    checks = run_checks(diff, "glovo")

    assert len(checks) == 5
    assert {c.ruleId for c in checks} == {"G1", "G2", "G3", "G4", "G5"}
    assert all(c.result == "fail" for c in checks), [
        (c.ruleId, c.result) for c in checks if c.result != "fail"
    ]


def test_glovo_agents_md_drives_severity() -> None:
    path = Path("glovo/AGENTS.md")
    original = path.read_text()
    path.write_text(original.replace("G1 BLOCK:", "G1 WARN:"))
    try:
        checks = run_checks("+tip = float(x)\n", "glovo")
        g1 = next(c for c in checks if c.ruleId == "G1")
        assert g1.severity == "WARN", "severity must be driven by AGENTS.md"
    finally:
        path.write_text(original)


def _result(checks: list[object], rule_id: str) -> str:
    return next(check.result for check in checks if check.ruleId == rule_id)


def _severity(checks: list[object], rule_id: str) -> str:
    return next(check.severity for check in checks if check.ruleId == rule_id)
