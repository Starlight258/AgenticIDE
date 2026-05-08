from src.guardrails import check_patch

SAMPLE_PATCH = """\
+from .utils import calc
+def apply_discount(order, pct):
+    print(f"Discount applied: {pct}")
+    requests.get(provider_url)
"""


def test_r4_print_block():
    """R4 detects print() and returns BLOCK/fail."""
    checks = check_patch(SAMPLE_PATCH, "efood")
    r4 = next(c for c in checks if c.ruleId == "R4")
    assert r4.result == "fail"
    assert r4.severity == "BLOCK"


def test_r5_requests_block():
    """R5 detects direct requests call and returns BLOCK/fail."""
    checks = check_patch(SAMPLE_PATCH, "efood")
    r5 = next(c for c in checks if c.ruleId == "R5")
    assert r5.result == "fail"
    assert r5.severity == "BLOCK"


def test_r1_relative_import_warn():
    """R1 detects relative import and returns WARN/fail."""
    checks = check_patch(SAMPLE_PATCH, "efood")
    r1 = next(c for c in checks if c.ruleId == "R1")
    assert r1.result == "fail"
    assert r1.severity == "WARN"


def test_clean_patch_all_pass():
    """A clean patch with no violations passes all rules."""
    clean = "+from src.utils import calc\n+def _private(): pass\n"
    checks = check_patch(clean, "efood")
    assert all(c.result == "pass" for c in checks)


def test_r2_subprocess_block():
    """R2 detects subprocess usage and returns BLOCK/fail."""
    subproc = "+import subprocess\n+subprocess.run(['ls'])\n"
    checks = check_patch(subproc, "efood")
    r2 = next(c for c in checks if c.ruleId == "R2")
    assert r2.result == "fail"
    assert r2.severity == "BLOCK"


def test_brand_parameter_accepted():
    """check_patch accepts any brand string and returns 5 checks for empty patch."""
    checks = check_patch("", brand="glovo")
    assert len(checks) == 5
    assert all(c.result == "pass" for c in checks)
