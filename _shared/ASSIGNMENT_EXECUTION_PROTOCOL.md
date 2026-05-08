# Assignment Execution Protocol
# Agentic IDE IC1 Backend Engineer — Take-Home Playbook

> **How to use**: Give me this file + the assignment file at the start of a session.
> I will execute the phases below in order, using worktrees and parallel agents where specified.
> Target: 90%+ pass-rate output within the stated time budget.

---

## JD Signal Map — Read Before Any Code

Every implementation choice below maps to a JD keyword. If a choice is not on this map, it is P2.

| JD Keyword | What to show in code | Where it lands |
|---|---|---|
| `Git worktrees` | Two worktrees, parallel branches, explicit merge step | Phase 3 setup, commit history |
| `multi-agent` | Agent A (routes) + Agent B (guardrails) on separate worktrees | Phase 3 prompt framing |
| `AGENTS.md / Engineering Manifesto` | File loaded just-in-time in every LLM call; brand-specific override path described | `src/llm.py`, README §Architecture |
| `guardrails — safe to deploy` | `GuardrailCheck(ruleId, severity, result, reason)` — BLOCK stops merge | `src/guardrails.py`, README §Domain Model |
| `multi-brand (efood/glovo/talabat)` | `brand` field on Session; guardrail loader parametrized by brand | Schema, guardrail signature |
| `context integration` | AGENTS.md injected as system-prompt context, not hardcoded strings | `src/llm.py` system prompt |
| `OTEL / OAM / tracing` | `trace_id` on Session; P2 note for OAM export | Schema + README §If More Time |
| `deterministic boundary` | Regex-first guardrails; LLM only for plan/patch generation | README §Architecture diagram |
| `developer productivity / friction` | README §Problem opens with the manual workflow this replaces | README §1 Problem |
| `customizing cutting-edge agentic IDE` | "This is not a Cursor clone — it is the DH-aware integration layer above Cursor" | README §1 first line |
| `measurement / KPI` | `GuardrailCheck` output feeds PR/engineer and Human/AI code ratio dashboards | README §If More Time |

**Mandatory before submitting**: every row above must map to ≥1 line of code or README text.

---

## Design Principles — Apply Before Writing Any Schema or Route

These five principles gate every implementation decision. If a choice conflicts with one, stop and reconsider.

### 1. SRP — Single Responsibility per Endpoint

Each endpoint = one state transition = one responsibility.

| Endpoint | Responsibility | What it must NOT do |
|---|---|---|
| `POST /sessions` | Create session entity | Generate plan, touch LLM |
| `POST /sessions/{id}/plan` | Decompose description → `[PlanStep]` with `patches: []` | Generate diffs, run guardrails |
| `POST /sessions/{id}/steps/{step_id}/patches` | Generate diff for one PlanStep → `PatchProposal` with `checks: []` | Run guardrails, modify other steps |
| `POST /sessions/{id}/steps/{step_id}/patches/{patch_id}/check` | Run guardrails → `[GuardrailCheck]` | Generate new diffs, re-plan |
| `GET /sessions/{id}` | Return accumulated state | Trigger any computation |

**Smell check**: if a route calls both `generate()` and `check_patch()`, it violates SRP.

**Schema SRP corollary**: domain models (storage/response) and LLM input schemas are different things.
- Domain model: `PlanStep(id, description, target_files, patches=[])` — full state with children
- LLM input schema: `PlanStepInput(description, target_files)` — only what the LLM generates
- Never pass a domain model schema to the LLM if it contains nested children (id, created_at, child lists).
  The LLM will fill them in, breaking the SRP of every downstream endpoint.

---

### 2. Deterministic Boundary

The LLM is always sandwiched between deterministic code. Non-determinism is quarantined.

```
[deterministic in]  →  [LLM]  →  [deterministic out]
  schema validation     proposes    schema validation
  AGENTS.md load        only        guardrail regex
  brand resolution               Pydantic parsing
```

Rules:
- `src/guardrails.py` contains **zero** LLM calls. Regex only.
- `src/llm.py` contains **zero** business logic. It is a transport layer.
- LLM output is always parsed through Pydantic before it touches application state.
- Use `tool_use` + `tool_choice={"type":"tool","name":"output"}` — never free-text JSON parsing.

---

### 3. YAGNI — You Aren't Gonna Need It

Build exactly what the spec asks. Nothing more.

| Temptation | Decision |
|---|---|
| SQLite / Postgres | In-memory dict. Persistence is P2 — document the swap path. |
| Auth / API keys | Not in spec. Padding scope is a red flag for evaluators. |
| LLM-as-judge for guardrails | Regex covers R1–R5 exactly. LLM-as-judge is P2. |
| Retry loop / Evaluator-Optimizer | P2. Document it in README §If More Time. |
| Multi-brand AGENTS.md routing | `brand` parameter in signature. Second brand file is P2. |
| Caching | Not needed within a 90-min session lifetime. |

If it is not in the spec and not a JD signal, it is P2 — mention in README, do not implement.

**YAGNI applies to response shape too — Response Schema = Workflow Signal.**

The shape of a response communicates what the endpoint did. Empty child collections in a response are not "free" — they send a false signal.

```
# Wrong: POST /plan returns this
{"id": "...", "description": "...", "target_files": [...], "patches": []}
#                                                           ^^^^^^^^^^
#                                              implies patches are part of planning

# Right: POST /plan returns this
{"id": "...", "description": "...", "target_files": [...]}
# shape says: "I produced a plan step. patches are someone else's job."
```

Rule: **each endpoint's response schema contains only the fields that endpoint created.**
Use a dedicated response model (e.g. `PlanStepOut`, `PatchProposalOut`) without child lists — do not reuse the full domain model as the response type.

```python
# models.py — response schemas (one per endpoint that creates a new entity)
class PlanStepOut(BaseModel):
    id: UUID
    description: str
    target_files: list[str]
    # no patches — POST /plan does not create patches

class PatchProposalOut(BaseModel):
    id: UUID
    planStepId: UUID
    diff: str
    # no checks — POST /patches does not run guardrails
```

The full domain model (`PlanStep` with `patches`, `PatchProposal` with `checks`) is only used in `GET /sessions/{id}` — the accumulated state view.

---

### 4. Workflow-first Design

Design the workflow (sequence of state transitions) before designing schemas or routes.

**Step 1 — Draw the workflow as a state machine first:**
```
∅ → Session(steps=[]) → Session(steps=[PlanStep(patches=[])]) → Session(steps=[PlanStep(patches=[PatchProposal(checks=[])])]) → Session(steps=[...(checks=[GuardrailCheck...])])
```

**Step 2 — Each arrow = one endpoint.**
Each endpoint advances state by exactly one step. No endpoint skips a step or does two steps at once.

**Step 3 — Schema flows from workflow, not from database convenience.**
Ask: "what is the minimal input the LLM needs to do its job?" → that is the LLM input schema.
Ask: "what is the full state a reviewing engineer needs?" → that is the domain model.

---

### 5. Explainability

Every AI decision must be traceable by a human reviewer.

| Layer | Explainability mechanism |
|---|---|
| Plan generation | `PlanStep.description` is human-readable; `target_files` is explicit |
| Patch generation | `PatchProposal.diff` is a standard unified diff — reviewable in any diff tool |
| Guardrail result | `GuardrailCheck.ruleId` + `reason` — cites the specific AGENTS.md rule |
| Session audit | `Session.trace_id` — future OTEL/OAM hook |
| AI vs human work | README §AI Leverage table — explicit, honest accounting |

**Rule**: No GuardrailCheck result without a `reason` that names the specific rule (`per AGENTS.md R4`).
A `result: "fail"` with `reason: "error"` is worse than useless — it is unactionable.

---

## Meta-Principles (from Anthropic engineering blog + agent-architecture.md)

- **Deterministic sandwich**: Every LLM call sits between deterministic input validation and deterministic output verification. The LLM proposes; the code decides.
- **Workflow backbone + one agent loop**: LLM loop only where genuinely non-deterministic. Guardrails are always deterministic.
- **Just-in-time context**: Load AGENTS.md at call time — never pre-dump into module-level startup.
- **Single agent > multi-agent for the coding loop**: Use parallel worktrees for *independent implementation tracks*, not for agents collaborating on the same task.
- **README is the deliverable**: Code is proof it works. The README demonstrates you think like a system designer.
- **DH framing**: This service is a "DH-aware integration layer" — it augments Cursor/Claude Code with brand context and guardrails. It is not a replacement IDE.

---

## Phase 0 — Decompose (0:00 – 0:05)

**Who runs this**: Me (Claude Code), immediately on receiving the assignment.

### 0.1 XY-30S Decomposition (4 bullets, 30 seconds)

```
- WHO uses this?           → developer requesting an AI-assisted code change
- WHAT friction removed?   → manual diff review + rule compliance check against AGENTS.md
- NON-DETERMINISTIC parts? → plan decomposition, patch generation (LLM); rule checking (regex)
- EXTERNAL integrations?   → Anthropic API, AGENTS.md file, brand config
```

### 0.2 Risk Inventory

| Risk | Mitigation |
|------|-----------|
| LLM latency in tests | `ANTHROPIC_API_KEY` missing → mock mode; real call behind flag |
| Storage underspecified | In-memory dict; documented swap path to Postgres |
| Rule ambiguity in AGENTS.md | Regex-first; LLM-as-judge only if regex is insufficient |
| Multi-brand complexity | `brand` field drives AGENTS.md path; single override dict per brand |
| Time overrun | P0/P1/P2 locked before first line of code |

### 0.3 P0 / P1 / P2 Cut List

| Tier | Scope | Time |
|------|-------|------|
| **P0** | All 5 endpoints + 2 deterministic guardrails (R4, R5 minimum) + 1 pytest green | 0–75 min |
| **P1** | Real Anthropic SDK call with structured JSON output; `trace_id` on every response; brand-parametrized guardrail loader | 75–85 min |
| **P2** | OTEL export to OAM; SQLite persistence; multi-brand AGENTS.md override; auth; SKILL.md Skills pattern | README mention only |

---

## Phase 1 — README Skeleton + Domain Model (0:05 – 0:20)

### 1.1 README.md — Write the 5 sections in English, all blanks filled with placeholders

```markdown
# Session Backend — Agentic IDE Integration Layer

> This service is the DH-aware integration layer that sits above Cursor/Claude Code:
> it injects brand context (AGENTS.md), proposes code patches via LLM, and enforces
> guardrails before any generated diff can be merged.
> The LLM proposes; deterministic checks decide.

## 1. Problem & Approach

**What this replaces**: a developer manually reviewing LLM-generated diffs against
their brand's Engineering Manifesto (AGENTS.md) before merging.

**Architecture**: deterministic sandwich —
- deterministic input (AGENTS.md loaded just-in-time, brand resolved from session)
- LLM call (plan decomposition or patch generation, schema-constrained output)
- deterministic output (guardrail regex checks, severity-gated merge decision)

**Assumptions** (5+):
1. In-memory storage is sufficient for a session-scoped prototype; persistence is P2.
2. AGENTS.md lives at the repo root and is the authoritative rule source.
3. Severity BLOCK = merge blocked; WARN = visible to developer but not blocking.
4. LLM output is always validated against the Pydantic schema before storage.
5. Each brand (efood/glovo/talabat) can have its own AGENTS.md path; currently efood only.
6. `trace_id` is generated per-session for future OTEL export.

**Ambiguities I noticed**:
1. Should WARN rules accumulate across patches and block after N warnings?
2. Is the LLM allowed to propose changes to AGENTS.md itself?
3. Who owns rule addition — platform team or brand team?

## 2. Domain Model

- `Session` — top-level entity; carries `brand`, `trace_id`, and all child lists
- `PlanStep` — one proposed change (description + target_files)
- `PatchProposal` — unified diff string for one PlanStep
- `GuardrailCheck` — one rule result: `ruleId`, `severity`, `result`, `reason`

```
Session 1—* PlanStep 1—* PatchProposal 1—* GuardrailCheck
```

Severity ladder: `BLOCK` (security/brand violation) > `WARN` (style) > `INFO` (suggestion).
A patch with any `BLOCK` check cannot be merged. This feeds the Human/AI code ratio KPI
by flagging which AI-generated diffs required human intervention.

## 3. AI Leverage

| Part | Done by | Verification |
|------|---------|--------------|
| Domain models | Hand | Type-checked by Pydantic + mypy |
| FastAPI routes | AI (Claude Code, worktree feat/routes) | Hand-reviewed diff |
| Guardrail regex rules | AI (Claude Code, worktree feat/guardrails) | Pytest: R2/R4/R5 BLOCK cases |
| LLM prompt design | Hand | Manual smoke test with real API key |
| README | Hand | — |

Every AI-generated file went through: `ruff check` → `pytest` → manual diff scan.
No AI output was committed without a test covering the specific behavior.

"The LLM only performs extraction and proposal generation.
Merging, validation, and guardrail evaluation are deterministic."

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| In-memory storage | Removes DB setup from the critical path; session lifetime = single workflow | Sessions must survive server restart |
| Regex-first guardrails (not LLM-as-judge) | Deterministic, fast, testable; regex covers R1–R5 exactly | Rules become too nuanced for regex (e.g. "detect hardcoded secret") |
| Single-brand (efood) | Spec asks for one brand; multi-brand is a path, not a feature | Second brand onboards |
| No auth | Spec does not specify auth; adding it would pad scope, not signal | Service goes to staging |
| Direct Anthropic SDK (no LangChain) | Framework would obscure the prompt/response contract, making guardrails harder to test | Team standardizes on a shared LLM gateway |
| `trace_id` on every entity | Free — uuid4 at creation time; enables OTEL export without schema change | OAM integration is scoped |

## 5. If More Time

- **OTEL export** → push `trace_id` spans to DH OAM (Observability & Monitoring); ties into PR/engineer KPI dashboard
- **Multi-brand AGENTS.md override** → parametrize loader by `brand`; each brand maintains its own manifesto
- **SKILL.md Skills pattern** (Anthropic open standard) → per-brand capability packages loadable just-in-time
- **SQLite persistence** → swap in-memory dict for SQLite; no schema change required (Pydantic models already serialize cleanly)
- **LLM-as-judge for style rules** → R3 (docstrings) is hard to catch with regex; second-pass LLM eval for WARN-tier rules
- **Evaluator-Optimizer loop** → let LLM re-propose patch after BLOCK guardrail fails, up to N retries

## How to Run

```bash
uv sync
cp .env.example .env     # set ANTHROPIC_API_KEY (or leave blank for mock mode)
uv run pytest            # all tests green
uv run uvicorn src.main:app --reload
# → http://localhost:8000/docs
```

Full workflow:
```bash
# 1. create session
SESSION=$(curl -s -X POST localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"add discount","description":"add pricing/discount.py","brand":"efood"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. plan
curl -s -X POST localhost:8000/sessions/$SESSION/plan | python3 -m json.tool

# 3. patch (use planStepId from step 2)
PATCH=$(curl -s -X POST localhost:8000/sessions/$SESSION/patches \
  -H "Content-Type: application/json" \
  -d '{"planStepId":"<id>"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. check — expect R4 and R5 to flag BLOCK
curl -s -X POST localhost:8000/sessions/$SESSION/patches/$PATCH/check | python3 -m json.tool
```
```

### 1.2 Pydantic Schemas — data shape only, zero logic

Three kinds of models. Do not confuse them.

| Kind | Purpose | Rule |
|---|---|---|
| **LLM input schema** | What we ask the LLM to generate | Only fields the LLM creates. No id, no timestamps, no child lists. |
| **Response schema (Out)** | What each endpoint returns to the caller | Only fields that endpoint created. No child lists belonging to later endpoints. |
| **Domain model** | Storage + `GET /sessions/{id}` full state | Nested children: steps → patches → checks. Never use as LLM input or single-step response. |

**Never pass a domain model schema to the LLM.** Child lists (`patches`, `checks`) will be filled in by the LLM, silently collapsing separate endpoints into one — violating SRP and Workflow-first.

**Never return a domain model directly from a mutating endpoint.** Returning `PlanStep` (which includes `patches: []`) from `POST /plan` falsely implies the plan step owns patching — a structural lie in the API contract.

File: `src/models.py`

```python
from uuid import uuid4, UUID
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field

Brand = Literal["efood", "glovo", "talabat"]
Severity = Literal["BLOCK", "WARN", "INFO"]
CheckResult = Literal["pass", "fail"]


# ── LLM Input Schemas ─────────────────────────────────────────────────────────

class PlanStepInput(BaseModel):
    description: str
    target_files: list[str]

class PatchProposalInput(BaseModel):
    diff: str


# ── Response Schemas (Out) ────────────────────────────────────────────────────

class PlanStepOut(BaseModel):
    """POST /plan response — no patches (Response Shape = Workflow Signal)."""
    id: UUID
    description: str
    target_files: list[str]

class PatchProposalOut(BaseModel):
    """POST /patches response — no checks (SRP: patch ≠ check)."""
    id: UUID
    planStepId: UUID
    diff: str
    created_at: datetime


# ── Domain Models ─────────────────────────────────────────────────────────────

class GuardrailCheck(BaseModel):
    ruleId: str
    severity: Severity
    result: CheckResult
    reason: str                     # must cite specific rule: "per AGENTS.md R4"

class PatchProposal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    planStepId: UUID
    diff: str
    checks: list[GuardrailCheck] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PlanStep(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    description: str
    target_files: list[str]
    patches: list[PatchProposal] = []

class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    brand: Brand
    trace_id: UUID = Field(default_factory=uuid4)   # OTEL hook
    steps: list[PlanStep] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

**Success gate**: `uv run python -c "from src.models import Session, PlanStep, PatchProposal, GuardrailCheck, PlanStepInput, PatchProposalInput, PlanStepOut, PatchProposalOut"` exits 0.

**Design principle check**:
- `PlanStepInput` / `PatchProposalInput` exist and are separate from domain models (SRP) ✓
- `PlanStepOut` / `PatchProposalOut` exist and omit child lists (Response Shape = Workflow Signal) ✓
- `brand: Brand` — multi-brand (JD signal) ✓
- `trace_id` — OTEL hook (JD signal) ✓
- `reason: str` — explainability: cites AGENTS.md rule ✓

---

## Phase 2 — Architecture Diagram in README (0:20 – 0:25)

Add this to README §1 before writing any route. This diagram is what the evaluator reads in 30 seconds to assess system thinking.

```
Architecture — Deterministic Sandwich:

Developer Request
        │
        ▼
[POST /sessions]
  brand: "efood" → resolves AGENTS.md path         ← deterministic

[POST /sessions/{id}/plan]
  load AGENTS.md just-in-time                       ← deterministic
  → LLM(claude-sonnet-4-6): decompose → [PlanStep] ← non-deterministic, schema-constrained
  → validate: target_files non-empty               ← deterministic

[POST /sessions/{id}/steps/{step_id}/patches]
  → LLM: generate unified diff for PlanStep        ← non-deterministic
  → store as PatchProposal(diff=...)

[POST /sessions/{id}/steps/{step_id}/patches/{patch_id}/check]
  → load AGENTS.md for brand just-in-time          ← deterministic
  → for each rule: regex check → GuardrailCheck    ← deterministic
  → any BLOCK? → merge gated                       ← deterministic

[GET /sessions/{id}]
  → full state: steps + patches + checks + trace_id
```

**Opening sentence** (copy verbatim into README §1):
> "This service converts implicit human debugging workflows into explicit, observable agent workflows — the LLM proposes, deterministic checks decide."

**Positioning sentence** (copy verbatim, 2nd line of README intro):
> "It is not a Cursor clone — it is the DH-aware integration layer that injects brand context (AGENTS.md) and enforces Engineering Manifesto guardrails before any AI-generated patch can be merged."

---

## Phase 3 — Implementation (0:25 – 1:15)

### Worktree Setup — Explicit JD Signal

The worktree split is **not just an efficiency choice** — it demonstrates the JD requirement: "Git worktrees and modern development workflows." Name the branches so the git log tells the story.

```bash
# From repo root (main branch already has models.py)
git worktree add ../wt-routes -b feat/routes-llm-integration
git worktree add ../wt-guardrails -b feat/guardrails-deterministic
```

Both agents run concurrently. Each sees the same `src/models.py` (committed to main before Phase 3).

---

### Agent A Prompt — Routes + LLM Integration (worktree: wt-routes)

```
You are implementing the FastAPI routes for a DH Agentic IDE session backend.
Branch: feat/routes-llm-integration. Worktree: ../wt-routes.
src/models.py is already committed on main — do NOT modify it.

Positioning context (important for README alignment):
This service is the "DH-aware integration layer" above Cursor/Claude Code.
It injects AGENTS.md (the brand's Engineering Manifesto) as just-in-time context
into every LLM call — not as a pre-loaded module variable.

Files to create:
  src/llm.py    — LLM client wrapper
  src/routes.py — 5 FastAPI route handlers
  src/main.py   — app factory + router registration + /health

1. src/llm.py
   - Two functions: generate(prompt, brand, schema) -> dict  and  generate_list(prompt, brand, schema) -> list[dict]
   - Loads AGENTS.md for the brand just-in-time: Path(f"{brand}/AGENTS.md").read_text()
   - Uses tool_use for structured output — NEVER free-text JSON parsing:
       tools=[{"name":"output","description":"...","input_schema": schema.model_json_schema()}]
       tool_choice={"type":"tool","name":"output"}
       result = response.content[0].input   # already a dict, no json.loads needed
   - max_tokens=4096 minimum
   - generate_list wraps schema in: {"type":"object","properties":{"items":{"type":"array","items":schema.model_json_schema()}},"required":["items"]}
     and returns result["items"]
   - If ANTHROPIC_API_KEY not set: return deterministic mock (do not crash)
   - CRITICAL: routes call generate(prompt, brand, PlanStepInput) and generate(prompt, brand, PatchProposalInput)
     — NEVER generate(prompt, brand, PlanStep) or generate(prompt, brand, PatchProposal)
     — Domain models contain child lists; passing them to LLM violates SRP
   - Functions ≤ 30 lines. No print(). Use logging.

2. src/routes.py — all routes use sessions: dict[str, Session] from src/store.py

   Use three-tier schemas — NEVER return a domain model from a mutating endpoint:
   - LLM calls: generate(prompt, brand, PlanStepInput), generate(prompt, brand, PatchProposalInput)
   - POST /plan response_model=list[PlanStepOut] — return PlanStepOut per step (no patches field)
   - POST /patches response_model=PatchProposalOut — return PatchProposalOut (no checks field)
   - GET /sessions/{id} response_model=Session — only endpoint that returns full nested state

   POST /sessions
     body: {title, description, brand}
     → Session(title=..., description=..., brand=...)
     → store in dict, return session

   POST /sessions/{id}/plan
     → call generate_list(prompt, brand, PlanStepInput) → list[dict]
     → steps = [PlanStep(**s) for s in raw_steps]; attach to session.steps
     → return [PlanStepOut(id=s.id, description=s.description, target_files=s.target_files) for s in steps]

   POST /sessions/{id}/steps/{step_id}/patches
     step_id is a path param — no request body needed
     → call generate(prompt, brand, PatchProposalInput) → dict
     → patch = PatchProposal(**raw, planStepId=step.id); attach to step.patches
     → return PatchProposalOut(id=patch.id, planStepId=patch.planStepId, diff=patch.diff, created_at=patch.created_at)

   POST /sessions/{id}/steps/{step_id}/patches/{patch_id}/check
     → import check_patch from src.guardrails (stub: raise ImportError gracefully if missing)
     → attach results to patch.checks, return list[GuardrailCheck]

   GET /sessions/{id}
     → return full Session (all nested lists included)

3. src/store.py
   sessions: dict[str, Session] = {}

Constraints:
- All imports absolute (from src.models import ...)
- ruff check must pass
- No print() anywhere

Done when: uvicorn src.main:app starts and GET /health returns {"status": "ok"}.
```

---

### Agent B Prompt — Guardrails + Tests (worktree: wt-guardrails)

```
You are implementing the deterministic guardrail layer for a DH Agentic IDE session backend.
Branch: feat/guardrails-deterministic. Worktree: ../wt-guardrails.
src/models.py is already committed on main — do NOT modify it.

JD context:
The guardrail is what makes AI-generated code "safe to deploy."
It implements the Engineering Manifesto (AGENTS.md) as code-enforced policy.
Every rule must produce a GuardrailCheck with ruleId, severity, result, and reason.

File: src/guardrails.py

  def check_patch(patch_text: str, brand: str) -> list[GuardrailCheck]:
      """Evaluate a unified diff against the brand's AGENTS.md rules.
      Returns one GuardrailCheck per rule, regardless of pass/fail.
      brand parameter is present for future multi-brand AGENTS.md routing.
      """

Rules (regex-based, deterministic — no LLM calls in this file):

  R1 — Absolute imports only
    Pattern: line in diff starting with +, containing "from ." (relative import)
    Severity: WARN
    Reason template: "Relative import detected: '{match}' — use absolute imports per AGENTS.md R1"

  R2 — No os.system or subprocess without review
    Pattern: + line containing "os.system(" or "subprocess."
    Severity: BLOCK
    Reason template: "Unsafe shell call '{match}' — requires explicit security review per AGENTS.md R2"

  R3 — Public functions must have docstrings
    Pattern: + line matching `def [a-z][^_]` (public, non-dunder) not followed by a + line with """
    Severity: WARN
    Reason: "Public function missing docstring per AGENTS.md R3"

  R4 — No print() — use efood.logging
    Pattern: + line containing "print("
    Severity: BLOCK
    Reason template: "print() call detected — use efood.logging per AGENTS.md R4"

  R5 — External HTTP via efood.http_client only
    Pattern: + line containing "requests." (get/post/put/delete/patch)
    Severity: BLOCK
    Reason template: "Direct requests.{method} call — use efood.http_client per AGENTS.md R5"

Return one GuardrailCheck per rule, always. If no violation found: result="pass".

File: tests/test_guardrails.py

  SAMPLE_PATCH (use this for multi-rule tests):
    +from .utils import calc
    +def apply_discount(order, pct):
    +    print(f"Discount applied: {pct}")
    +    requests.get(provider_url)

  test_r4_print_block: SAMPLE_PATCH → R4 result="fail", severity="BLOCK"
  test_r5_requests_block: SAMPLE_PATCH → R5 result="fail", severity="BLOCK"
  test_r1_relative_import_warn: SAMPLE_PATCH → R1 result="fail", severity="WARN"
  test_clean_patch_all_pass: clean patch (no violations) → all result="pass"
  test_r2_subprocess_block: patch with "subprocess.run(" → R2 result="fail", severity="BLOCK"
  test_brand_parameter_accepted: check_patch("", brand="glovo") does not raise

Done when: uv run pytest tests/test_guardrails.py -v shows 6 tests passing.
```

---

### Merge + Integration (after both agents complete)

```bash
cd /path/to/main-repo
git merge feat/routes-llm-integration
git merge feat/guardrails-deterministic

# Wire guardrail into /check route:
# src/routes.py: replace `return []` stub with:
#   from src.guardrails import check_patch
#   results = check_patch(patch.diff, session.brand)
```

Verify integration:
```bash
uv run pytest                        # all tests green
uv run uvicorn src.main:app --reload # server starts
```

---

## Phase 4 — E2E Validation (1:15 – 1:25)

Unit tests verify code correctness. This phase verifies **feature correctness** — the evaluator's actual test.

```bash
# 1. create efood session
SESSION=$(curl -s -X POST localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"discount module","description":"add pricing/discount.py with apply_discount","brand":"efood"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'])")

echo "Session: $SESSION"

# 2. plan
STEP=$(curl -s -X POST localhost:8000/sessions/$SESSION/plan \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'])")

echo "Step: $STEP"

# 3. patch
PATCH=$(curl -s -X POST localhost:8000/sessions/$SESSION/steps/$STEP/patches \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Patch: $PATCH"

# 4. check — MUST see R4 and R5 as BLOCK
curl -s -X POST localhost:8000/sessions/$SESSION/steps/$STEP/patches/$PATCH/check \
  | python3 -m json.tool

# 5. full state
curl -s localhost:8000/sessions/$SESSION | python3 -m json.tool
```

**Pass criteria**:
- R4 (`print`) → `severity: "BLOCK"`, `result: "fail"` ✓
- R5 (`requests`) → `severity: "BLOCK"`, `result: "fail"` ✓
- `trace_id` present on Session ✓
- Full state returns nested steps → patches → checks ✓

---

## Phase 5 — README Finalize + JD Alignment (1:25 – 1:30)

Fill every blank in the skeleton. Then run the JD alignment check below.

### JD Alignment Check (must all be green before submit)

| JD Requirement | Evidence in repo | ✓ |
|---|---|---|
| Git worktrees | `git log --oneline --graph` shows feat/routes + feat/guardrails merged | ☐ |
| Multi-agent workflow | README §3 AI Leverage table shows Agent A / Agent B with separate worktrees | ☐ |
| AGENTS.md / Engineering Manifesto | README §Architecture: "loaded just-in-time"; code: `src/llm.py` reads file at call time | ☐ |
| Guardrails — safe to deploy | `GuardrailCheck.severity=BLOCK` gates merge; R4 + R5 demonstrated in E2E | ☐ |
| Multi-brand field | `Session.brand: Brand` in schema; `check_patch(patch, brand=session.brand)` in route | ☐ |
| OTEL / OAM / tracing | `Session.trace_id` present; README §5 names OAM export as P2 | ☐ |
| Deterministic boundary | README diagram shows LLM between two deterministic blocks; guardrails are regex-only | ☐ |
| Context integration framing | README intro: "DH-aware integration layer" not "build an IDE" | ☐ |
| Developer productivity / friction | README §1 opens with "what this replaces" — the manual workflow | ☐ |
| Measurement / KPI | README §Domain Model mentions Human/AI code ratio as downstream metric | ☐ |

### Design Principles Check (run before JD alignment)

| Principle | Verification |
|---|---|
| SRP — POST /plan response has no `patches` field | `curl .../plan \| python3 -c "import json,sys; d=json.load(sys.stdin); assert 'patches' not in d[0]"` |
| SRP — POST /patches response has no `checks` field | Same pattern: `assert 'checks' not in d` |
| SRP — LLM input schemas exist and are separate | `grep -n "PlanStepInput\|PatchProposalInput" src/models.py` shows two classes |
| SRP — Response schemas (Out) exist and are separate | `grep -n "PlanStepOut\|PatchProposalOut" src/models.py` shows two classes |
| Deterministic Boundary — no LLM call in guardrails.py | `grep -n "anthropic\|client\." src/guardrails.py` returns nothing |
| YAGNI — no unspecified features | No SQLite, no auth, no retry loop unless spec asked |
| Workflow-first — GET /sessions/{id} shows accumulated state | Full nested state only after all endpoints called in sequence |
| Explainability — reason cites rule | `grep "per AGENTS.md" src/guardrails.py` returns one line per rule |

**All 10 green = submit. Any red = fix README or add one line of code.**

---

## Commit Strategy

```bash
git add src/models.py README.md
git commit -m "feat: domain model + README skeleton (schemas, architecture, assumptions)"

git merge feat/routes-llm-integration
git commit -m "feat: FastAPI routes + LLM integration (just-in-time AGENTS.md context)"

git merge feat/guardrails-deterministic
git commit -m "feat: deterministic guardrails R1-R5 (BLOCK/WARN/INFO) + pytest"

# wire integration
git add src/routes.py
git commit -m "feat: wire guardrail into /check route, E2E smoke tested"

git add README.md
git commit -m "docs: trade-offs, assumptions, JD alignment, AI leverage table"
```

Commit messages are part of the submission. Each one should read like a PR title, not a diary entry.

---

## Signal Phrases for README (copy, then customize)

```
README intro (2 sentences max):
"This service converts implicit human debugging workflows into explicit, observable
agent workflows — the LLM proposes, deterministic checks decide.
It is not a Cursor clone — it is the DH-aware integration layer that injects
brand context (AGENTS.md) and enforces Engineering Manifesto guardrails before
any AI-generated patch can be merged."

AI Leverage section (mandate):
"The LLM only performs extraction and proposal generation.
Merging, validation, and guardrail evaluation are deterministic."

Trade-off (scope control):
"I intentionally deferred [X] because [Y] mattered more within the [N]-hour constraint.
I would reconsider if [Z]."

Multi-brand extensibility (show architectural thinking):
"The guardrail loader accepts brand as a parameter.
Adding glovo would mean: create glovo/AGENTS.md, add 'glovo' to the Brand literal.
No route code changes required."

OTEL mention (shows production mindset):
"trace_id is generated at session creation and propagated to every GuardrailCheck.
In production, these would be exported as OTEL spans to DH OAM."
```

---

## Anti-Patterns to Avoid

1. **Framework-first** — No LangChain, no LlamaIndex. Direct `anthropic` SDK only.
2. **Context dump** — Do NOT load AGENTS.md into a module-level variable at startup. Just-in-time.
3. **LLM for guardrails** — R1–R5 are regex. LLM-as-judge is P2, named as such in README.
4. **print() anywhere** — Use `logging`. This is also a test case.
5. **README last** — Skeleton (all 5 sections + Architecture diagram) before first route.
6. **E2E skip** — Pytest green ≠ feature correct. Always run the curl workflow.
7. **Missing brand on guardrail** — `check_patch(diff, brand)` signature must accept brand even if unused now.
8. **No trace_id** — It is one field, costs nothing, and signals OTEL/OAM awareness from the start.
9. **"multi-brand" only in schema** — It must also appear in README as a described extension path.
10. **Worktrees not visible in git log** — Merge commits should show feat/routes and feat/guardrails branch names.

---

## File Output Map

```
src/
  models.py      ← Phase 1 (hand-written schemas)
  store.py       ← Phase 3 Agent A (in-memory dict)
  llm.py         ← Phase 3 Agent A (just-in-time AGENTS.md + Anthropic call)
  routes.py      ← Phase 3 Agent A (5 FastAPI routes)
  guardrails.py  ← Phase 3 Agent B (regex R1–R5, brand-parametrized)
  main.py        ← Phase 3 Agent A (app factory + /health)
tests/
  test_guardrails.py  ← Phase 3 Agent B (6 test cases)
{brand}/
  AGENTS.md      ← provided; loaded just-in-time (path: f"{brand}/AGENTS.md")
README.md        ← Phase 1 skeleton, Phase 5 filled
.env.example     ← ANTHROPIC_API_KEY=  (empty = mock mode)
```
