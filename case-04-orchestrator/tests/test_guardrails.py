from pathlib import Path

import pytest

from src.guardrails import GuardrailCheck, run_checks

SAMPLE_PATCH = """
+from .utils import calc
+def apply_discount(order, pct):
+    print(f"Discount applied: {pct}")
+    requests.get(provider_url)
"""


def _by_rule(diff: str, brand: str = "efood") -> dict[str, GuardrailCheck]:
    return {check.ruleId: check for check in run_checks(diff, brand)}


def test_r4_print_block() -> None:
    check = _by_rule(SAMPLE_PATCH)["R4"]

    assert check.result == "fail"
    assert check.severity == "BLOCK"
    assert "per AGENTS.md R4" in check.reason


def test_r5_requests_block() -> None:
    check = _by_rule(SAMPLE_PATCH)["R5"]

    assert check.result == "fail"
    assert check.severity == "BLOCK"
    assert "per AGENTS.md R5" in check.reason


def test_clean_patch_all_pass() -> None:
    clean_patch = """
+from src.pricing import calc
+def apply_discount(order, pct):
+    \"\"\"Apply a percentage discount.\"\"\"
+    return calc(order.total, pct)
"""

    checks = run_checks(clean_patch, "efood")

    assert {check.result for check in checks} == {"pass"}


def test_agents_md_drives_severity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    brand_dir = tmp_path / "efood"
    brand_dir.mkdir()
    (tmp_path / "AGENTS.md").write_text("- R1 WARN: Absolute imports only\n")
    (brand_dir / "AGENTS.md").write_text("- R1 BLOCK: Absolute imports only\n")
    monkeypatch.chdir(tmp_path)

    check = _by_rule("+from .x import y", "efood")["R1"]

    assert check.result == "fail"
    assert check.severity == "BLOCK"
