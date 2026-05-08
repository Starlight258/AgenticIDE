# Session Backend — Agentic IDE Integration Layer

> This service is the DH-aware integration layer that sits above Cursor/Claude Code:
> it injects brand context (AGENTS.md), proposes code patches via LLM, and enforces
> guardrails before any generated diff can be merged.
> The LLM proposes; deterministic checks decide.
>
> It is not a Cursor clone — it is the DH-aware integration layer that injects
> brand context (AGENTS.md) and enforces Engineering Manifesto guardrails before
> any AI-generated patch can be merged.

---

## 1. Problem & Approach

**What this replaces**: a developer manually reviewing LLM-generated diffs against
their brand's Engineering Manifesto (AGENTS.md) before merging — an error-prone,
slow step that blocked AI-assisted coding from being trusted at merge time.

**Architecture — Deterministic Sandwich**:

```
Developer Request
        │
        ▼
[POST /sessions]
  brand: "efood" → resolves efood/AGENTS.md path         ← deterministic

[POST /sessions/{id}/plan]
  load efood/AGENTS.md just-in-time                       ← deterministic
  → LLM(claude-sonnet-4-6): decompose → [PlanStep]       ← non-deterministic, schema-constrained
  → validate: target_files non-empty                      ← deterministic

[POST /sessions/{id}/patches]
  → LLM: generate unified diff for one PlanStep           ← non-deterministic
  → store as PatchProposal(diff=...)

[POST /sessions/{id}/patches/{id}/check]
  → load efood/AGENTS.md just-in-time                     ← deterministic
  → for each rule R1–R5: regex check → GuardrailCheck     ← deterministic
  → any BLOCK? → merge gated                              ← deterministic

[GET /sessions/{id}]
  → full state: steps + patches + checks + trace_id
```

The LLM only performs extraction and proposal generation.
Merging, validation, and guardrail evaluation are deterministic.

Each endpoint is a single transition — plan, patch, and check are kept separate so that
each AI-assisted step is independently reviewable and deterministic guardrail evaluation
stays decoupled from LLM generation. POST /plan returns `patches: []`; patches are only
created when POST /patches is explicitly called.

**Assumptions**:
1. In-memory storage is sufficient for a session-scoped prototype; persistence is P2.
2. `efood/AGENTS.md` is the authoritative rule source, loaded just-in-time per request.
3. Severity `BLOCK` = merge blocked; `WARN` = visible to developer, not blocking.
4. LLM output is always validated against the Pydantic schema before storage.
5. Each brand (efood/glovo/talabat) can have its own `{brand}/AGENTS.md`; currently efood only.
6. `trace_id` is generated per-session as a hook for future OTEL export.
7. Mock mode activates automatically when `ANTHROPIC_API_KEY` is absent — no test failures.

**Ambiguities I noticed**:
1. Should WARN-tier violations accumulate across patches and block after N warnings?
2. Is the LLM permitted to propose changes to `AGENTS.md` itself?
3. Who owns rule addition — platform team or brand team?

---

## 2. Domain Model

- `Session` — top-level entity; carries `brand`, `trace_id`, and all child lists
- `PlanStep` — one proposed change (description + target_files)
- `PatchProposal` — unified diff string for one PlanStep
- `GuardrailCheck` — one rule result: `ruleId`, `severity`, `result`, `reason`

```
Session 1—* PlanStep 1—* PatchProposal 1—* GuardrailCheck
```

Severity ladder: `BLOCK` (security/brand violation) > `WARN` (style) > `INFO` (suggestion).
A patch with any `BLOCK` check cannot be merged. This feeds the **Human/AI code ratio KPI**
by flagging which AI-generated diffs required human intervention before merge.

---

## 3. AI Leverage

| Part | Done by | Verification |
|------|---------|--------------|
| Domain models (`src/models.py`) | Hand | Type-checked by Pydantic |
| FastAPI routes (`src/routes.py`) | AI — Claude Code, worktree `feat/routes-llm-integration` | Hand-reviewed diff + E2E smoke test |
| LLM client (`src/llm.py`) | AI — Claude Code, worktree `feat/routes-llm-integration` | Manual smoke test with real API key |
| Guardrail rules (`src/guardrails.py`) | AI — Claude Code, worktree `feat/guardrails-deterministic` | Pytest: R1/R2/R4/R5 BLOCK/WARN cases |
| Tests (`tests/test_guardrails.py`) | AI — Claude Code, worktree `feat/guardrails-deterministic` | `uv run pytest` green |
| README | Hand | — |

Every AI-generated file went through: `ruff check` → `uv run pytest` → manual diff scan.
No AI output was committed without a test covering the specific behavior.

---

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| In-memory storage | Removes DB from critical path; session lifetime = single workflow | Sessions must survive server restart |
| Regex-first guardrails (not LLM-as-judge) | Deterministic, fast, testable; regex covers R1–R5 exactly | Rules become too nuanced for regex (e.g. detect hardcoded secret semantically) |
| Single-brand (efood) | Spec asks for one brand; multi-brand is an extension path, not a feature | Second brand onboards — add `{brand}/AGENTS.md` + Brand literal |
| No auth | Spec does not specify auth; adding it would pad scope, not signal | Service goes to staging |
| Direct Anthropic SDK (no LangChain) | Framework would obscure the prompt/response contract, making guardrails harder to test | Team standardizes on a shared LLM gateway |
| `trace_id` on Session | uuid4 at creation time — zero cost; enables OTEL export without schema change | OAM integration is scoped |
| Parallel worktrees (routes + guardrails) | Routes and guardrails are independent; parallel branches demonstrate modern workflow and reduce wall-clock time | Branches diverge and merge conflicts become frequent |

---

## 5. If More Time

- **OTEL export** → push `trace_id` spans to DH OAM; ties into PR/engineer KPI dashboard
- **Multi-brand AGENTS.md override** → `brand` field already in schema; add `glovo/AGENTS.md`, extend `Brand` literal — no route changes needed
- **SKILL.md Skills pattern** (Anthropic open standard) → per-brand capability packages loaded just-in-time
- **SQLite persistence** → swap `dict[str, Session]` for SQLite; Pydantic models serialize cleanly with `.model_dump()`
- **LLM-as-judge for style rules** → R3 (docstrings) is difficult with regex; second-pass LLM eval for WARN-tier rules
- **Evaluator-Optimizer loop** → LLM re-proposes patch after BLOCK guardrail fails, up to N retries
- **Human/AI code ratio tracking** → count `result="pass"` vs `result="fail"` GuardrailChecks per session → feed into KPI dashboard

---

## How to Run

```bash
uv sync
cp .env.example .env     # set ANTHROPIC_API_KEY (or leave blank for mock mode)
uv run pytest            # all tests green
uv run uvicorn src.main:app --reload
# → http://localhost:8000/docs
```

Full workflow (efood session with sample discount patch):

```bash
# 1. create session
SESSION=$(curl -s -X POST localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"add discount module","description":"add pricing/discount.py with apply_discount function","brand":"efood"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. plan
STEP=$(curl -s -X POST localhost:8000/sessions/$SESSION/plan \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. patch
PATCH=$(curl -s -X POST localhost:8000/sessions/$SESSION/patches \
  -H "Content-Type: application/json" \
  -d "{\"planStepId\":\"$STEP\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. check — expect R4 (print) and R5 (requests) to flag BLOCK
curl -s -X POST localhost:8000/sessions/$SESSION/patches/$PATCH/check \
  | python3 -m json.tool

# 5. full state
curl -s localhost:8000/sessions/$SESSION | python3 -m json.tool
```
