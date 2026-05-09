# CODEX_PROMPTS.md - case-02-session

## 실행 순서

1. **Prompt #0**: codex에 붙여넣기 (foundation 파일 생성 + 커밋)
2. **워크트리 설정**: bash 명령어 직접 실행
3. **Prompt #1**: wt-routes 워크트리의 codex 세션에 붙여넣기
4. **Prompt #2**: wt-guardrails 워크트리의 codex 세션에 붙여넣기 (#1과 동시)
5. **Prompt #3**: 둘 다 끝나면 wire-up
6. **Prompt #4**: 최종 검증 + README 완성

각 prompt 끝에 "commit 전에 멈춰. diff와 commit message 3개 보여줘. 내가 확인할 때까지 commit 하지 마."가 명시되어 있다.

---

### Prompt #0 - Foundation Setup

```
You are setting up the foundation for the case-02-session FastAPI service (glovo brand).
Working directory: case-02-session/ (cd into it first).

Create the following files exactly as specified.

────────────────────────────────────────────────────
FILE 1: glovo/AGENTS.md
────────────────────────────────────────────────────

# Glovo Engineering Rules

> Loaded as context for any AI agent working on glovo codebase.

## Guardrail Rules

- G1 BLOCK: All money/price arithmetic must use `Decimal`, never `float`. (correctness)
- G2 BLOCK: No hardcoded external URLs — must come from `glovo.config`. (security)
- G3 BLOCK: Async DB access must use `glovo.db.session` context manager, never `engine.connect()` directly. (brand)
- G4 WARN: Public handlers must propagate `X-Glovo-Trace-Id` into structured logs. (observability)
- G5 WARN: Public functions must include a docstring with at least one `Args:` line. (style)

## Code Style

- All domain models = pydantic `BaseModel` subclasses with explicit type hints.
- Functions <= 30 lines.
- No dead code, no TODO without a date.
- `ruff check` and `ruff format` must pass before commit.

## Multi-brand

- All entities carry a `brand` field: `"efood" | "glovo" | "talabat"`.
- Brand-specific rules override global rules.

────────────────────────────────────────────────────
FILE 2: glovo/sample_diff.patch
────────────────────────────────────────────────────

diff --git a/payments/charge.py b/payments/charge.py
new file mode 100644
index 0000000..0000001
--- /dev/null
+++ b/payments/charge.py
@@ -0,0 +1,18 @@
+from decimal import Decimal
+import logging
+
+URL = "https://api.partner.com/charge"
+
+logger = logging.getLogger(__name__)
+
+
+async def charge(order):
+    amount: Decimal = Decimal(str(order.amount))
+    tip = float(order.tip)
+    async with engine.connect() as conn:
+        result = await conn.execute(
+            "INSERT INTO charges VALUES (?, ?)", (amount, tip)
+        )
+    logger.info("Charged order", extra={"order_id": order.id})
+    return result

────────────────────────────────────────────────────
FILE 3: src/models.py
────────────────────────────────────────────────────

from uuid import UUID, uuid4
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]
ReadinessVerdict = Literal["READY", "NOT_READY"]


class GuardrailCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ruleId: str
    severity: Severity
    result: CheckResult
    reason: str


class PatchProposal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    step_id: UUID
    brand: Brand
    diff: str
    checks: list[GuardrailCheck] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlanStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    description: str
    target_files: list[str]
    patches: list[PatchProposal] = Field(default_factory=list)


class TestRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    patch_ids: list[UUID]
    outcome: Literal["PASS", "FAIL", "PARTIAL"]
    notes: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    brand: Brand
    trace_id: UUID = Field(default_factory=uuid4)
    steps: list[PlanStep] = Field(default_factory=list)
    test_runs: list[TestRun] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

────────────────────────────────────────────────────
FILE 4: src/schemas.py
────────────────────────────────────────────────────

from uuid import UUID
from datetime import datetime
from typing import Literal
from pydantic import BaseModel

from src.models import Brand, ReadinessVerdict


class SessionCreate(BaseModel):
    title: str
    description: str
    brand: Brand


class PlanStepInput(BaseModel):
    description: str
    target_files: list[str]


class PatchProposalInput(BaseModel):
    diff: str


class PlanStepOut(BaseModel):
    id: UUID
    description: str
    target_files: list[str]


class PatchProposalOut(BaseModel):
    id: UUID
    step_id: UUID
    diff: str
    created_at: datetime


class StepReadinessOut(BaseModel):
    step_id: UUID
    verdict: ReadinessVerdict
    block_count: int
    warn_count: int


class TestRunCreate(BaseModel):
    patch_ids: list[UUID]
    outcome: Literal["PASS", "FAIL", "PARTIAL"]
    notes: str = ""


class TestRunOut(BaseModel):
    id: UUID
    session_id: UUID
    patch_ids: list[UUID]
    outcome: Literal["PASS", "FAIL", "PARTIAL"]
    notes: str
    created_at: datetime

────────────────────────────────────────────────────
FILE 5: src/store.py
────────────────────────────────────────────────────

from src.models import Session

sessions: dict[str, Session] = {}

────────────────────────────────────────────────────
VERIFICATION
────────────────────────────────────────────────────

After creating all 5 files, run:

  uv run python -c "
  from src.models import Session, PlanStep, PatchProposal, GuardrailCheck, TestRun
  from src.schemas import (PlanStepInput, PatchProposalInput, PlanStepOut,
      PatchProposalOut, StepReadinessOut, TestRunOut, TestRunCreate, SessionCreate)
  print('imports OK')
  "

Must print "imports OK". If it fails, fix the error and re-run.

Then run:
  uv run ruff check src/

Must be clean.

Stage these files (do NOT use git add .):
  git add case-02-session/glovo/AGENTS.md
  git add case-02-session/glovo/sample_diff.patch
  git add case-02-session/src/models.py
  git add case-02-session/src/schemas.py
  git add case-02-session/src/store.py

Stop before commit. Show the git diff --staged and 3 commit message options. Wait for my confirmation.
```

---

### Worktree Setup (직접 실행 - Prompt #0 커밋 확인 후)

```bash
# repo root에서 실행
git worktree add ../wt-routes -b feat/case02-routes-llm
git worktree add ../wt-guardrails -b feat/case02-guardrails-tests
```

확인:
```bash
git worktree list
# ../wt-routes        [feat/case02-routes-llm]
# ../wt-guardrails    [feat/case02-guardrails-tests]
```

---

### Prompt #1 - Agent A: Routes + LLM

```
You are the Builder Agent implementing the FastAPI routes and LLM integration for case-02-session.
Branch: feat/case02-routes-llm. Worktree: ../wt-routes.
Working directory inside the worktree: case-02-session/

IMPORTANT: src/models.py and src/schemas.py are already committed on main. Do NOT modify them.
CRITICAL: load_dotenv() must be the FIRST call in main.py, before any local imports.

────────────────────────────────────────────────────
CONTEXT
────────────────────────────────────────────────────

This service is the glovo-aware integration layer above Cursor/Claude Code.
It injects glovo/AGENTS.md (the brand Engineering Manifesto) as just-in-time context into every LLM call.
The LLM proposes; deterministic checks decide.

Brand: glovo
Rules G1-G5 are defined in glovo/AGENTS.md.
Trust boundary: LLM produces Plan + Patch. Service computes CheckResult. Reviewer records TestRun.

────────────────────────────────────────────────────
FILE 1: src/llm.py
────────────────────────────────────────────────────

Two functions: generate_plan(title, description, brand) -> list[PlanStepInput]
               generate_patch(step_description, target_files, brand) -> PatchProposalInput

Rules:
- Load glovo/AGENTS.md just-in-time: Path(f"{brand}/AGENTS.md").read_text()
  Never load at module level. Load inside the function call.
- Use tool_use for structured output — NEVER free-text JSON:
    tools=[{"name":"output","description":"...","input_schema": schema}]
    tool_choice={"type":"tool","name":"output"}
    result = response.content[0].input   # already a dict, no json.loads needed
- max_tokens=4096 minimum
- If ANTHROPIC_API_KEY not set or empty: return deterministic mock (do not crash)
  Mock for generate_plan: [PlanStepInput(description="stub step", target_files=["payments/charge.py"])]
  Mock for generate_patch: PatchProposalInput(diff="--- /dev/null\n+++ b/payments/charge.py\n@@ -0,0 +1 @@\n+pass")
- Use logging not print()
- NEVER call generate_plan(brand=brand, schema=PlanStep) — only PlanStepInput schema
- NEVER call generate_patch(brand=brand, schema=PatchProposal) — only PatchProposalInput schema

────────────────────────────────────────────────────
FILE 2: src/routes.py
────────────────────────────────────────────────────

Import: from src.store import sessions
Import domain models from src.models, schemas from src.schemas.
router = APIRouter()

Implement these 7 endpoints exactly:

1. POST /sessions
   Body: SessionCreate
   Action: create Session(title=body.title, description=body.description, brand=body.brand)
           store in sessions dict, key = str(session.id)
   Response: Session (full domain model)

2. POST /sessions/{session_id}/plan
   Action: lookup session or raise HTTPException(404)
           call generate_plan(session.title, session.description, session.brand) -> list[PlanStepInput]
           for each: create PlanStep(description=inp.description, target_files=inp.target_files)
                     validate target_files is non-empty, raise 422 if empty
           set session.steps = created steps
   Response: list[PlanStepOut] — return PlanStepOut(id=s.id, description=s.description, target_files=s.target_files) per step
             DO NOT return patches field — PlanStepOut has no patches

3. POST /sessions/{session_id}/plan/{step_id}/patches
   Action: lookup session (404 if missing), lookup step in session.steps (404 if missing)
           call generate_patch(step.description, step.target_files, session.brand) -> PatchProposalInput
           create PatchProposal(step_id=step.id, brand=session.brand, diff=inp.diff)
           append to step.patches
   Response: PatchProposalOut — DO NOT return checks field

4. POST /sessions/{session_id}/patches/{patch_id}/check
   Action: lookup session (404), find patch across all steps (404 if not found)
           try: from src.guardrails import run_checks
           except ImportError: raise HTTPException(503, "guardrails not available")
           results = run_checks(patch.diff, session.brand)
           patch.checks = results
   Response: list[GuardrailCheck]

5. GET /sessions/{session_id}/plan/{step_id}/readiness
   Action: lookup session (404), lookup step (404)
           find the most recently created patch that has checks (len(patch.checks) > 0)
           if no such patch: return StepReadinessOut(step_id=step.id, verdict="NOT_READY", block_count=0, warn_count=0)
           latest_checked = max of patches with checks, sorted by created_at
           block_count = sum(1 for c in latest_checked.checks if c.result == "fail" and c.severity == "BLOCK")
           warn_count = sum(1 for c in latest_checked.checks if c.result == "fail" and c.severity == "WARN")
           verdict = "NOT_READY" if block_count > 0 else "READY"
   Response: StepReadinessOut

6. POST /sessions/{session_id}/test-runs
   Body: TestRunCreate
   Action: lookup session (404)
           validate all body.patch_ids exist somewhere in session.steps[*].patches (422 if any missing)
           create TestRun(session_id=session.id, patch_ids=body.patch_ids, outcome=body.outcome, notes=body.notes)
           append to session.test_runs
   Response: TestRunOut

7. GET /sessions/{session_id}
   Action: lookup session (404)
   Response: Session (full nested state: steps > patches > checks + test_runs + trace_id)

────────────────────────────────────────────────────
FILE 3: src/main.py (update existing)
────────────────────────────────────────────────────

Replace the existing file entirely:

from dotenv import load_dotenv
load_dotenv()

import logging
from fastapi import FastAPI
from src.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="case-02-session — glovo Agentic IDE Backend")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

────────────────────────────────────────────────────
DONE CRITERIA
────────────────────────────────────────────────────

1. uv run ruff check src/ — clean
2. uv run uvicorn src.main:app starts without error
3. curl -s localhost:8000/health returns {"status":"ok"}

Stage only changed files:
  git add case-02-session/src/llm.py
  git add case-02-session/src/routes.py
  git add case-02-session/src/main.py

Stop before commit. Show the git diff --staged and 3 commit message options. Wait for my confirmation.
```

---

### Prompt #2 - Agent B: Guardrails + Tests

```
You are the Builder Agent implementing the deterministic guardrail layer and tests for case-02-session.
Branch: feat/case02-guardrails-tests. Worktree: ../wt-guardrails.
Working directory inside the worktree: case-02-session/

IMPORTANT: src/models.py and src/schemas.py are already committed on main. Do NOT modify them.
This file has ZERO LLM calls. Regex only.

────────────────────────────────────────────────────
CONTEXT
────────────────────────────────────────────────────

The guardrail is what makes AI-generated code "safe to deploy."
It implements glovo/AGENTS.md rules as code-enforced policy.
AGENTS.md must be the source of truth for severities — never hardcode "BLOCK" or "WARN" as literals
in the rule dispatch list itself. Read them from the file.

────────────────────────────────────────────────────
FILE 1: src/guardrails.py
────────────────────────────────────────────────────

import re
import logging
from pathlib import Path
from src.models import GuardrailCheck, Brand

logger = logging.getLogger(__name__)


def _parse_severities(brand: Brand) -> dict[str, str]:
    """Read {brand}/AGENTS.md and parse rule severities.
    Falls back to hardcoded defaults only if the file is missing.
    """
    try:
        text = Path(f"{brand}/AGENTS.md").read_text()
    except FileNotFoundError:
        logger.warning("AGENTS.md not found for brand %s, using defaults", brand)
        return {"G1": "BLOCK", "G2": "BLOCK", "G3": "BLOCK", "G4": "WARN", "G5": "WARN"}
    pattern = re.compile(r"-\s+(G\d+)\s+(BLOCK|WARN|INFO):")
    result = {m.group(1): m.group(2) for m in pattern.finditer(text)}
    return result or {"G1": "BLOCK", "G2": "BLOCK", "G3": "BLOCK", "G4": "WARN", "G5": "WARN"}


def run_checks(diff: str, brand: Brand) -> list[GuardrailCheck]:
    """Evaluate a unified diff against the brand's AGENTS.md rules.
    Returns exactly 5 GuardrailCheck objects (one per rule G1-G5), always.
    """
    severities = _parse_severities(brand)
    added = [line[1:] for line in diff.split("\n") if line.startswith("+") and not line.startswith("+++")]
    return [
        _check_g1(added, severities.get("G1", "BLOCK")),
        _check_g2(added, severities.get("G2", "BLOCK")),
        _check_g3(added, severities.get("G3", "BLOCK")),
        _check_g4(added, severities.get("G4", "WARN")),
        _check_g5(added, severities.get("G5", "WARN")),
    ]


def _check_g1(added: list[str], severity: str) -> GuardrailCheck:
    for line in added:
        if re.search(r"\bfloat\(", line):
            return GuardrailCheck(ruleId="G1", severity=severity, result="fail",
                reason=f"float() usage detected - per glovo/AGENTS.md G1")
    return GuardrailCheck(ruleId="G1", severity=severity, result="pass",
        reason="No float() usage in added lines")


def _check_g2(added: list[str], severity: str) -> GuardrailCheck:
    for line in added:
        m = re.search(r"""["'](https?://[^"']{4,})["']""", line)
        if m:
            return GuardrailCheck(ruleId="G2", severity=severity, result="fail",
                reason=f"Hardcoded URL '{m.group(1)}' - must come from glovo.config per AGENTS.md G2")
    return GuardrailCheck(ruleId="G2", severity=severity, result="pass",
        reason="No hardcoded external URLs in added lines")


def _check_g3(added: list[str], severity: str) -> GuardrailCheck:
    for line in added:
        if re.search(r"engine\.(connect|begin)\(", line):
            return GuardrailCheck(ruleId="G3", severity=severity, result="fail",
                reason="Direct engine.connect() usage - must use glovo.db.session per AGENTS.md G3")
    return GuardrailCheck(ruleId="G3", severity=severity, result="pass",
        reason="No direct DB session access in added lines")


def _check_g4(added: list[str], severity: str) -> GuardrailCheck:
    has_log = any(re.search(r"(logger|logging)\.(info|warning|error|debug)\(", line) for line in added)
    has_trace = any(re.search(r"trace_id|X-Glovo-Trace-Id", line) for line in added)
    if has_log and not has_trace:
        return GuardrailCheck(ruleId="G4", severity=severity, result="fail",
            reason="Log call without trace_id propagation - per glovo/AGENTS.md G4")
    return GuardrailCheck(ruleId="G4", severity=severity, result="pass",
        reason="trace_id propagation check passed")


def _check_g5(added: list[str], severity: str) -> GuardrailCheck:
    for i, line in enumerate(added):
        if re.match(r"\s*(?:async\s+)?def\s+[a-z]\w*\(", line):
            rest = [l for l in added[i + 1:] if l.strip()]
            first = rest[0] if rest else ""
            if not re.match(r'\s*["\']', first):
                fn = re.search(r"def\s+(\w+)", line)
                name = fn.group(1) if fn else "unknown"
                return GuardrailCheck(ruleId="G5", severity=severity, result="fail",
                    reason=f"Public function '{name}' missing docstring with Args: - per glovo/AGENTS.md G5")
    return GuardrailCheck(ruleId="G5", severity=severity, result="pass",
        reason="All public functions have docstrings")

────────────────────────────────────────────────────
FILE 2: tests/conftest.py
────────────────────────────────────────────────────

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from src.main import app
import src.store as store_module


@pytest.fixture(autouse=True)
def clear_store():
    store_module.sessions.clear()
    yield
    store_module.sessions.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_llm():
    with patch("src.llm.anthropic") as mock_anthropic:
        mock_response = MagicMock()
        mock_response.content = [MagicMock(input={
            "items": [{"description": "stub step", "target_files": ["payments/charge.py"]}]
        })]
        mock_anthropic.Anthropic.return_value.messages.create.return_value = mock_response
        yield mock_anthropic

────────────────────────────────────────────────────
FILE 3: tests/test_guardrails.py
────────────────────────────────────────────────────

Write these test cases. Each must pass.

SAMPLE_DIFF: read from glovo/sample_diff.patch
  Path("glovo/sample_diff.patch").read_text()
  This diff has float(order.tip), URL="https://...", engine.connect(), no docstring, logger without trace_id.
  Expected: all 5 rules fail.

Test cases:

1. test_sample_diff_all_five_fail:
   checks = run_checks(Path("glovo/sample_diff.patch").read_text(), "glovo")
   assert len(checks) == 5
   assert all(c.result == "fail" for c in checks)

2. test_g1_float_block:
   diff = "+tip = float(order.amount)\n"
   checks = run_checks(diff, "glovo")
   g1 = next(c for c in checks if c.ruleId == "G1")
   assert g1.result == "fail"
   assert g1.severity == "BLOCK"

3. test_g2_hardcoded_url_block:
   diff = '+URL = "https://api.partner.com/charge"\n'
   g2 = next(c for c in run_checks(diff, "glovo") if c.ruleId == "G2")
   assert g2.result == "fail"
   assert g2.severity == "BLOCK"

4. test_g3_direct_db_block:
   diff = "+    async with engine.connect() as conn:\n"
   g3 = next(c for c in run_checks(diff, "glovo") if c.ruleId == "G3")
   assert g3.result == "fail"
   assert g3.severity == "BLOCK"

5. test_g4_log_without_trace_warn:
   diff = '+    logger.info("charged", extra={"order_id": 1})\n'
   g4 = next(c for c in run_checks(diff, "glovo") if c.ruleId == "G4")
   assert g4.result == "fail"
   assert g4.severity == "WARN"

6. test_g5_no_docstring_warn:
   diff = "+async def charge(order):\n+    pass\n"
   g5 = next(c for c in run_checks(diff, "glovo") if c.ruleId == "G5")
   assert g5.result == "fail"
   assert g5.severity == "WARN"

7. test_clean_diff_all_pass:
   diff = '+    amount = Decimal(str(order.amount))\n+    return amount\n'
   checks = run_checks(diff, "glovo")
   assert all(c.result == "pass" for c in checks)

8. test_agents_md_drives_severity:
   # Temporarily modify glovo/AGENTS.md to set G1 to WARN instead of BLOCK
   path = Path("glovo/AGENTS.md")
   original = path.read_text()
   modified = original.replace("G1 BLOCK:", "G1 WARN:")
   path.write_text(modified)
   try:
       diff = "+tip = float(order.amount)\n"
       g1 = next(c for c in run_checks(diff, "glovo") if c.ruleId == "G1")
       assert g1.severity == "WARN", "severity must come from AGENTS.md, not hardcoded"
   finally:
       path.write_text(original)

────────────────────────────────────────────────────
FILE 4: tests/test_e2e.py
────────────────────────────────────────────────────

Full workflow test using TestClient. The mock_llm fixture in conftest.py is already in scope.

Write one test: test_full_workflow

Steps:
1. POST /sessions with {"title":"add charge","description":"add payments/charge.py","brand":"glovo"}
   assert response.status_code == 200
   session_id = response.json()["id"]
   assert "trace_id" in response.json()

2. POST /sessions/{session_id}/plan
   assert response.status_code == 200
   steps = response.json()
   assert len(steps) >= 1
   assert "patches" not in steps[0]   # SRP: POST /plan does not create patches
   step_id = steps[0]["id"]

3. POST /sessions/{session_id}/plan/{step_id}/patches
   assert response.status_code == 200
   patch = response.json()
   assert "checks" not in patch        # SRP: POST /patches does not run guardrails
   patch_id = patch["id"]

4. POST /sessions/{session_id}/patches/{patch_id}/check
   assert response.status_code == 200
   checks = response.json()
   assert len(checks) == 5

5. GET /sessions/{session_id}/plan/{step_id}/readiness
   assert response.status_code == 200
   readiness = response.json()
   assert readiness["step_id"] == step_id
   assert readiness["verdict"] in ["READY", "NOT_READY"]

6. POST /sessions/{session_id}/test-runs
   body = {"patch_ids": [patch_id], "outcome": "PASS", "notes": "smoke test passed"}
   assert response.status_code == 200
   run = response.json()
   assert run["outcome"] == "PASS"
   assert patch_id in run["patch_ids"]

7. GET /sessions/{session_id}
   assert response.status_code == 200
   state = response.json()
   assert len(state["steps"]) >= 1
   assert len(state["steps"][0]["patches"]) >= 1
   assert len(state["steps"][0]["patches"][0]["checks"]) == 5
   assert len(state["test_runs"]) == 1
   assert "trace_id" in state

────────────────────────────────────────────────────
DONE CRITERIA
────────────────────────────────────────────────────

uv run pytest tests/test_guardrails.py tests/test_e2e.py -v
All tests must pass. 0 failures, 0 errors.
uv run ruff check src/ — clean.

Stage only changed files:
  git add case-02-session/src/guardrails.py
  git add case-02-session/tests/conftest.py
  git add case-02-session/tests/test_guardrails.py
  git add case-02-session/tests/test_e2e.py

Stop before commit. Show the git diff --staged and 3 commit message options. Wait for my confirmation.
```

---

### Prompt #3 - Wire Integration

```
Both worktrees are merged. Working directory: case-02-session/

Step 1: Check that imports work end-to-end.
  uv run python -c "from src.guardrails import run_checks; print('guardrails OK')"
  uv run python -c "from src.routes import router; print('routes OK')"

Step 2: Run full test suite.
  uv run pytest -v
  Must be 0 failures.
  uv run ruff check src/

Step 3: Run smoke test (server must be running: uv run uvicorn src.main:app &)
  SESSION_FILE=/tmp/session.json
  curl -s -X POST localhost:8000/sessions \
    -H "Content-Type: application/json" \
    -d '{"title":"charge endpoint","description":"add payments/charge.py","brand":"glovo"}' \
    -o $SESSION_FILE
  python3 -c "import json; d=json.load(open('/tmp/session.json')); print('session_id:', d['id'])"
  SESSION=$(python3 -c "import json; print(json.load(open('/tmp/session.json'))['id'])")

  PLAN_FILE=/tmp/plan.json
  curl -s -X POST localhost:8000/sessions/$SESSION/plan -o $PLAN_FILE
  STEP=$(python3 -c "import json; print(json.load(open('/tmp/plan.json'))[0]['id'])")
  python3 -c "import json; d=json.load(open('/tmp/plan.json')); assert 'patches' not in d[0], 'FAIL: patches should not be in POST /plan response'"

  PATCH_FILE=/tmp/patch.json
  curl -s -X POST localhost:8000/sessions/$SESSION/plan/$STEP/patches -o $PATCH_FILE
  PATCH=$(python3 -c "import json; print(json.load(open('/tmp/patch.json'))['id'])")
  python3 -c "import json; d=json.load(open('/tmp/patch.json')); assert 'checks' not in d, 'FAIL: checks should not be in POST /patches response'"

  CHECK_FILE=/tmp/check.json
  curl -s -X POST localhost:8000/sessions/$SESSION/patches/$PATCH/check -o $CHECK_FILE
  python3 -c "
  import json
  checks = json.load(open('/tmp/check.json'))
  print('checks:', len(checks))
  for c in checks:
      print(c['ruleId'], c['severity'], c['result'])
  assert len(checks) == 5, 'must return exactly 5 checks'
  "

  READINESS_FILE=/tmp/readiness.json
  curl -s localhost:8000/sessions/$SESSION/plan/$STEP/readiness -o $READINESS_FILE
  python3 -c "import json; d=json.load(open('/tmp/readiness.json')); print('verdict:', d['verdict'], 'blocks:', d['block_count'])"

  TESTRUN_FILE=/tmp/testrun.json
  curl -s -X POST localhost:8000/sessions/$SESSION/test-runs \
    -H "Content-Type: application/json" \
    -d "{\"patch_ids\":[\"$PATCH\"],\"outcome\":\"PASS\",\"notes\":\"smoke test\"}" \
    -o $TESTRUN_FILE
  python3 -c "import json; d=json.load(open('/tmp/testrun.json')); print('test run outcome:', d['outcome'])"

  STATE_FILE=/tmp/state.json
  curl -s localhost:8000/sessions/$SESSION -o $STATE_FILE
  python3 -c "
  import json
  state = json.load(open('/tmp/state.json'))
  assert 'trace_id' in state
  assert len(state['steps']) >= 1
  assert len(state['steps'][0]['patches']) >= 1
  assert len(state['steps'][0]['patches'][0]['checks']) == 5
  assert len(state['test_runs']) == 1
  print('SMOKE TEST PASSED')
  "

If smoke test fails: fix the issue, re-run uv run pytest -v, re-run smoke test.
Do NOT commit until smoke test passes.

Stage changed files (only files you modified in this step):
  git add <specific files only>

Stop before commit. Show git diff --staged and 3 commit message options. Wait for my confirmation.
```

---

### Prompt #4 - JD Alignment + Requirements Gate + README

```
Working directory: case-02-session/
All tests must be green and smoke test must have passed before this prompt.

────────────────────────────────────────────────────
STEP 1: JD Alignment Check (all must pass)
────────────────────────────────────────────────────

Run each check. Report ✓ or ✗.

1. glovo/AGENTS.md loaded just-in-time in llm.py:
   grep -En "AGENTS\.md|read_text" src/llm.py | grep -v "^\s*#"
   Must return >= 1 line.

2. AGENTS.md read in guardrails.py:
   grep -En "AGENTS\.md|_parse_severities|read_text" src/guardrails.py | grep -v "^\s*#"
   Must return >= 1 line.

3. No hardcoded severity literals in rule dispatch:
   python3 -c "
   import re
   src = open('src/guardrails.py').read()
   # Count BLOCK/WARN literals NOT inside _parse_severities fallback dict
   lines = src.split('\n')
   in_parse = False
   count = 0
   for line in lines:
       if '_parse_severities' in line: in_parse = True
       if in_parse and 'return' in line and '{' in line: in_parse = False
       if not in_parse and re.search(r'[\"\'](BLOCK|WARN)[\"\']\s*,', line):
           count += 1
   print(f'Hardcoded severities outside fallback: {count} (must be 0)')
   "

4. LLM uses tool_use:
   grep -En "tool_choice" src/llm.py | grep -v "^\s*#"
   Must return >= 1 line.

5. No json.loads on LLM response:
   grep -En "json\.loads" src/llm.py | grep -v "^\s*#" | grep -v test
   Must return 0 lines.

6. max_tokens >= 4096:
   python3 -c "
   import re
   text = open('src/llm.py').read()
   hits = re.findall(r'max_tokens\s*=\s*(\d+)', text)
   bad = [h for h in hits if int(h) < 4096]
   if bad: print(f'FAIL: max_tokens too low: {bad}')
   else: print(f'max_tokens OK: {hits}')
   "

7. trace_id on Session:
   grep -En "trace_id" src/models.py | grep -v "^\s*#"
   Must return >= 1 line.

8. No print() in src/:
   result=$(grep -rEn "^\s*print\s*\(" src/ | grep -v "test_")
   [ -z "$result" ] && echo "No print() OK" || echo "FAIL: $result"

9. POST /plan response has no patches field:
   grep -n "PlanStepOut" src/routes.py
   grep -n "patches" src/schemas.py
   PlanStepOut must NOT have a patches field.

10. POST /patches response has no checks field:
    PatchProposalOut must NOT have a checks field.

11. Git worktrees visible in log:
    git log --oneline --graph | head -20
    Branch names feat/case02-routes-llm and feat/case02-guardrails-tests must appear.

────────────────────────────────────────────────────
STEP 2: Assignment Requirements Gate
────────────────────────────────────────────────────

Fill in this report. Every [ ] must become [x].

=== Phase 6: Assignment Requirements Gate ===
Assignment: case-02-session/assignment.md

ENDPOINTS
[ ] POST /sessions               — creates session with title, description, brand; returns id + trace_id
[ ] POST /sessions/{id}/plan     — LLM proposes steps; returns list[PlanStepOut] (no patches field)
[ ] POST /sessions/{id}/plan/{stepId}/patches  — LLM proposes diff; returns PatchProposalOut (no checks field)
[ ] POST /sessions/{id}/patches/{patchId}/check — returns 5 GuardrailCheck (G1-G5, ruleId/severity/result/reason)
[ ] GET  /sessions/{id}/plan/{stepId}/readiness — returns StepReadinessOut with verdict/block_count/warn_count
[ ] POST /sessions/{id}/test-runs — creates TestRun with patch_ids/outcome/notes
[ ] GET  /sessions/{id}           — returns full nested state (steps > patches > checks + test_runs + trace_id)

MUST CLAUSES
[ ] G1~G5 severities come from glovo/AGENTS.md, not hardcoded
    Evidence: grep src/guardrails.py for _parse_severities
[ ] sample_diff.patch triggers all 5 rules (5/5 fail)
    Evidence: test_sample_diff_all_five_fail passes

WE EVALUATE
[ ] step readiness decision and defense: SPEC.md 결정 2 설명 (가장 최근 체크된 패치 기준)
[ ] README: decisions, trade-offs, what you didn't do
[ ] README: how-to-run in under 1 minute
[ ] pytest: N passed, 0 failed
[ ] AI usage honest accounting in README

RESULT: [ALL PASS] or [FAIL: list items still open]

────────────────────────────────────────────────────
STEP 3: Update README.md
────────────────────────────────────────────────────

Update the existing README.md with these 5 sections:

## 1. Problem & Approach

Opening (copy verbatim):
"This service converts implicit human debugging workflows into explicit, observable agent workflows.
The LLM proposes; deterministic checks decide."

Positioning (copy verbatim):
"It is not a Cursor clone. It is the DH-aware integration layer that injects brand context (glovo/AGENTS.md)
and enforces Engineering Manifesto guardrails before any AI-generated patch can be merged."

**What this replaces**: a developer manually reading LLM-generated diffs and checking each one against
G1-G5 rules from glovo/AGENTS.md.

**Architecture**: deterministic sandwich
- deterministic input: glovo/AGENTS.md loaded just-in-time, brand resolved from session
- LLM call: plan decomposition or patch generation, schema-constrained output (tool_use)
- deterministic output: G1-G5 regex checks, BLOCK gates step readiness

**Assumptions**:
1. In-memory storage sufficient for session-scoped prototype; SQLite swap path in §5.
2. glovo/AGENTS.md is the authoritative source for rule severities.
3. BLOCK = step NOT_READY; WARN = visible but not blocking.
4. Step readiness = most recently checked patch only. Previous patches irrelevant.
5. LLM output always validated against Pydantic schema before storage.
6. trace_id generated per session for future OTEL export.

**Ambiguities I noticed**:
1. Should WARN accumulate across patches and block after N warnings? I chose: no.
2. Should multiple patches in a step be tested together or individually? I chose: TestRun links multiple patch_ids.

## 2. Domain Model

Session > PlanStep (multiple) > PatchProposal (multiple per step) > GuardrailCheck (5 per patch)
Session > TestRun (multiple, references multiple PatchProposals)

Key trust boundary:
| Resource    | Created by    |
|-------------|---------------|
| Plan/Patch  | LLM           |
| CheckResult | Service (regex) |
| TestRun     | Reviewer / CI |

Severity: BLOCK (G1/G2/G3) > WARN (G4/G5)
A step with any BLOCK check on its most recent checked patch cannot be merged.

## 3. AI Leverage

| Part               | Done by                              | Verification          |
|--------------------|--------------------------------------|----------------------|
| Domain models      | Hand                                 | Pydantic + type check |
| FastAPI routes     | AI (Agent A, feat/case02-routes-llm) | Hand-reviewed diff   |
| Guardrail rules    | AI (Agent B, feat/case02-guardrails-tests) | pytest all-5-fail test |
| LLM prompt design  | Hand                                 | Manual smoke test    |
| README             | Hand                                 |                      |

"The LLM only performs plan decomposition and patch generation.
Merging, validation, and guardrail evaluation are deterministic."

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| Step readiness = latest checked patch only | Matches actual dev flow: fix and re-patch; old failures don't block current work | Need full patch audit trail |
| Immutable check results | Check is a verification event; re-check means create new patch | Patch content could be edited in place |
| TestRun at session level (not step level) | Real tests run multiple changes at once | Tests must be scoped per step |
| In-memory storage | Removes DB setup from critical path | Sessions must survive restart |
| Regex-first guardrails | Deterministic, fast, testable; covers G1-G5 exactly | Rules too nuanced for regex |
| No auth | Not in spec; padding scope is a red flag | Service goes to staging |

## 5. If More Time

- **SQLite persistence**: replace in-memory dict; Pydantic models already serialize cleanly
- **OTEL export**: push trace_id spans to DH OAM; ties into PR quality KPI dashboard
- **Multi-brand AGENTS.md routing**: parametrize loader by brand; add glovo/efood/talabat AGENTS.md files
- **LLM-as-judge for G5**: docstring presence is hard to enforce with regex alone; second-pass LLM eval
- **Evaluator-Optimizer loop**: re-propose patch after BLOCK guardrail fails, up to N retries
- **Auth + ownership**: HTTPBearer token; session.owner_id field already present in schema

## How to Run

\`\`\`bash
cd case-02-session
uv sync
cp .env.example .env     # set ANTHROPIC_API_KEY (or leave blank for mock mode)
uv run pytest -v         # all tests green
uv run uvicorn src.main:app --reload
# open http://localhost:8000/docs
\`\`\`

────────────────────────────────────────────────────
STEP 4: Cross-check README vs code
────────────────────────────────────────────────────

Verify every endpoint mentioned in README exists in src/routes.py:
  grep -n "router\.\(post\|get\)" src/routes.py

Verify every claim in README §3 AI Leverage has a corresponding git branch:
  git log --oneline --graph | grep -E "case02-routes|case02-guardrails"

If any mismatch: fix README or add the missing code.

────────────────────────────────────────────────────
FINAL
────────────────────────────────────────────────────

Stage:
  git add case-02-session/README.md

Stop before commit. Show git diff --staged and 3 commit message options. Wait for my confirmation.
```
