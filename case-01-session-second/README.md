# efood AI Coding Session Guardrails

> FastAPI service that hosts efood AI coding sessions, asks Claude only for plan and patch proposals, and runs deterministic R1-R5 guardrails before merge review.
>
> It is not a CI runner, auth layer, queue, or persistent patch database. It is the deterministic policy gate around LLM-generated coding diffs.

---

## 1. Problem & Approach

**What this replaces**: a manual workflow where a developer asks an AI for a plan or diff, then reviewers have to remember and consistently apply efood's AGENTS.md rules before risky code reaches production.

**Architecture**:

```
[Request]
    |
    v
[POST /sessions]
  create Session with server-side id, trace_id, created_at, steps=[]      <- deterministic

[POST /sessions/{session_id}/plan]
  load Session by UUID                                                    <- deterministic
  -> Claude tool_use output: list of plan steps                           <- non-deterministic, schema-constrained
  -> Pydantic validates PlanStepInput, store saves PlanStep objects       <- deterministic

[POST /sessions/{session_id}/patches]
  load Session and step_id                                                <- deterministic
  -> Claude tool_use output: unified diff                                 <- non-deterministic, schema-constrained
  -> Pydantic validates PatchProposalInput, store saves PatchProposal     <- deterministic

[POST /patches/{patch_id}/check]
  load PatchProposal by globally unique patch_id                          <- deterministic
  -> regex guardrails inspect added diff lines only                       <- deterministic
  -> store overwrites checks on each call                                 <- deterministic

[GET /sessions/{session_id}]
  -> full state: Session -> steps -> patches -> checks
```

The LLM proposes work; deterministic Python decides whether the proposed patch passes, warns, or blocks under R1-R5.

**Actual endpoints**:

| Method | Path | Response model |
|--------|------|----------------|
| `GET` | `/health` | `dict[str, str]` |
| `POST` | `/sessions` | `Session` |
| `POST` | `/sessions/{session_id}/plan` | `list[PlanStepOut]` |
| `POST` | `/sessions/{session_id}/patches` | `PatchProposalOut` |
| `POST` | `/patches/{patch_id}/check` | `list[GuardrailCheck]` |
| `GET` | `/sessions/{session_id}` | `Session` |

**Assumptions**:
1. Storage is process-local memory in `src/store.py`; restart clears sessions and patches.
2. efood policy lives in `efood/AGENTS.md` and is implemented as regex checks in `src/guardrails.py`.
3. `BLOCK` means a merge gate must fail, `WARN` means reviewer attention is required, and `INFO` is available in the schema but not currently emitted by R1-R5.
4. LLM output is accepted only through Anthropic `tool_use` and Pydantic validation; domain models are not passed to the LLM.
5. `brand` accepts `efood`, `glovo`, or `talabat` at the schema layer, but only the efood rules are implemented.
6. `trace_id` is generated and returned on `Session`; there is no OTEL or distributed tracing.
7. If `ANTHROPIC_API_KEY` is absent, `src/llm.py` returns deterministic mock plan and patch data for tests and local demos.

**Ambiguities I noticed**:
1. The schema accepts `glovo` and `talabat`, but the spec says not to build multi-brand routing; this implementation stores the brand and applies the same efood guardrails.
2. R3 defines "public function without docstring" for added lines only; this implementation checks whether the next non-empty added line after `def name(...)` starts with a triple-quoted docstring.
3. The service returns guardrail checks, not a separate merge decision object; downstream callers must interpret any `BLOCK` failure as not mergeable.

---

## 2. Domain Model

- `Session` - one AI coding session with title, description, brand, trace_id, steps, and created_at.
- `PlanStep` - one LLM-proposed implementation step with target files and nested patches.
- `PatchProposal` - one LLM-proposed unified diff tied to a plan step and brand.
- `GuardrailCheck` - one deterministic R1-R5 result, including pass results as well as failures.

```
Session 1--* PlanStep 1--* PatchProposal 1--* GuardrailCheck
```

Severity ladder: `BLOCK` > `WARN` > `INFO`.
The check output is intended to feed a merge gate or review dashboard that can block on failed `BLOCK` rules.

---

## 3. Key Design Decisions

The hardest part of this problem was keeping LLM usefulness without letting the LLM decide policy.

### Guardrail Enforcement

**Option 1 - Ask the LLM to review patches**
The same model that proposes a diff also judges whether it follows R1-R5.
Risk: identical patches can receive different judgments, which is unacceptable for a merge gate.

**Option 2 - Deterministic regex checks on full diff text**
Apply regex rules across the whole patch.
Risk: removed lines, file headers, or context lines can create false failures.

**Option 3 - Deterministic regex checks on added lines only**
Inspect lines that start with `+` while excluding `+++` diff headers.
Risk: complex Python semantics are not modeled, but the specified R1-R5 patterns are covered directly.

**I chose Option 3** because it gives stable, repeatable results for the exact policy surface in the spec. The trade-off is that this is a guardrail scanner, not a general static analyzer. I would reconsider if AGENTS.md gained semantic rules that require parsing Python ASTs or cross-file context.

### Patch Check Scope

**Option 1 - `/sessions/{session_id}/patches/{patch_id}/check`**
Scope checks under sessions.
Risk: callers must carry redundant IDs even though patch IDs are UUIDs.

**Option 2 - `/patches/{patch_id}/check`**
Check by globally unique patch ID.
Risk: the URL does not visibly show the parent session.

**Option 3 - Compute checks during patch creation**
Always run guardrails inside `POST /sessions/{session_id}/patches`.
Risk: callers cannot explicitly re-run checks, and idempotent overwrite behavior is harder to demonstrate.

**I chose Option 2** because it matches the implementation spec and keeps patch checks simple. The trade-off is less hierarchical routing, which is acceptable because the patch ID is globally unique.

---

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| In-memory `dict` storage | Keeps the assignment focused on API shape, LLM contract, and guardrails. | Sessions must survive process restart or run across multiple workers. |
| Deterministic regex guardrails | R1-R5 are explicit string patterns, so deterministic checks are more reliable than LLM review. | Rules require Python AST analysis, dataflow, or repo-wide context. |
| LLM only for plan and patch generation | Keeps creative generation separate from merge policy. | The product needs natural-language explanation after deterministic checks complete. |
| `/patches/{patch_id}/check` URL | Patch UUIDs are globally unique, so session scope is redundant for the check call. | Patch IDs become scoped or human-readable rather than globally unique. |
| Store all five check results | Callers can see pass and fail outcomes for every R1-R5 rule. | Payload size becomes an issue after adding many more rules. |
| Idempotent check overwrite | Re-running `/check` replaces prior checks for the same patch. | Historical guardrail runs need audit retention. |
| No authentication or authorization | Explicitly out of scope for this service. | The API is exposed outside local or trusted test environments. |
| No DB, Redis, or persistence | Explicitly out of scope and unnecessary for the in-memory demo. | Production needs durability, concurrency, or audit trails. |
| No multi-brand routing | `brand` is stored, but only efood rules are implemented. | Glovo or talabat require different rule files or severity policies. |
| No async queue or streaming LLM | Requests are synchronous and simple to test. | Patch generation becomes slow or needs progress updates. |
| No OTEL or distributed tracing | Only a `trace_id` field exists today. | The service participates in production request tracing. |
| Direct Anthropic SDK with `tool_use` | It directly satisfies `tool_choice={"type":"tool","name":"output"}` and `max_tokens=4096`. | Multiple providers or richer orchestration become required. |

---

## 5. Edge Cases Considered

- Missing session ID returns `404`.
- Missing step ID inside an existing session returns `404`.
- Missing patch ID returns `404`.
- `/patches/{patch_id}/check` can be called repeatedly and overwrites `checks`.
- Unknown `brand` values fail at Pydantic request validation with `422`.
- Missing `ANTHROPIC_API_KEY` uses deterministic mock LLM output.
- Empty patch text returns five passing checks.
- Removed lines and diff headers are ignored because guardrails inspect added lines only.

For the most critical case, guardrail determinism is handled by never asking the LLM to judge policy. `src/guardrails.py` returns the same five checks for the same diff every time.

---

## 6. AI Usage Log

I used AI as a reasoning partner and implementation assistant. The implementation was checked against the spec, route decorators, response models, and tests.

Example prompts used during design:
- "How should the service separate LLM patch generation from deterministic policy checks?"
- "What edge cases should the FastAPI layer handle for missing sessions, steps, and patches?"
- "How can R1-R5 be implemented using only added lines in a unified diff?"
- "Review the README against `src/routes.py` so documented URLs match actual decorators."

Every implementation file was verified with `uv run ruff check`, `uv run ruff format --check`, and `uv run pytest`.

| Part | Done by | Verification |
|------|---------|--------------|
| `pyproject.toml` | AI-assisted | Dependency/import validation through `uv run pytest`; style through `uv run ruff check`. |
| `src/main.py` | AI-assisted | `GET /health` test and route import through FastAPI `TestClient`. |
| `src/models.py` | AI-assisted | Response-shape tests and Pydantic validation in `tests/test_e2e.py`. |
| `src/store.py` | AI-assisted | Nested session workflow and idempotent check test. |
| `src/routes.py` | AI-assisted | Endpoint coverage in `tests/test_e2e.py`; README URLs grepped from decorators. |
| `src/service.py` | AI-assisted | Full session workflow, 404 behavior, and check overwrite tests. |
| `src/llm.py` | AI-assisted | Mock-mode workflow tests without `ANTHROPIC_API_KEY`; tool-use contract checked by code review. |
| `src/guardrails.py` | AI-assisted | R1-R5 unit tests in `tests/test_guardrails.py`. |
| `tests/conftest.py` | AI-assisted | Store isolation confirmed by full pytest run. |
| `tests/test_guardrails.py` | AI-assisted | Exercises empty patch, added-line filtering, and each R1-R5 rule. |
| `tests/test_e2e.py` | AI-assisted | Exercises health, response shapes, validation, 404s, and idempotent checks. |
| `efood/AGENTS.md` | AI-assisted | Rule text cross-checked against `src/guardrails.py` and tests. |
| `README.md` | AI-assisted | Cross-checked against route decorators, models, tests, and spec exclusions. |

---

## 7. If More Time

- **Authentication and authorization** -> add caller identity, session ownership, and permission checks before exposing this API beyond trusted local use.
- **Persistence with DB or Redis** -> replace process-local dictionaries with durable storage and indexes for sessions, steps, patches, and check history.
- **Multi-brand routing** -> keep the existing `brand` field, add per-brand rule configuration, and route `glovo` and `talabat` to their own policies.
- **Async queue and streaming LLM** -> move slow plan/patch generation into background jobs and stream status or partial output.
- **OTEL and distributed tracing** -> export `trace_id` into spans and logs so guardrail outcomes can be followed across services.

---

## How to Run

```bash
uv sync
# Optional: set ANTHROPIC_API_KEY in your environment for real Claude calls.
# Without it, the service uses deterministic mock LLM responses.
uv run pytest
uv run uvicorn src.main:app --reload
# -> http://localhost:8000/docs
```

Healthcheck:

```bash
curl localhost:8000/health
# {"status":"ok"}
```

Full workflow:

```bash
# 1. Create a session.
SESSION_ID=$(curl -s -X POST localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"AI coding session","description":"Implement deterministic efood guardrails","brand":"efood"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Create plan steps for the session.
STEP_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/plan \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. Create a patch for one step.
PATCH_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/patches \
  -H "Content-Type: application/json" \
  -d "{\"step_id\":\"$STEP_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Run deterministic guardrails.
curl -s -X POST localhost:8000/patches/$PATCH_ID/check | python3 -m json.tool

# 5. Read full nested session state.
curl -s localhost:8000/sessions/$SESSION_ID | python3 -m json.tool
```

## Tested Working

- `GET /health` -> `{"status":"ok"}`.
- `POST /sessions` -> `Session` with `steps=[]`, server-generated `id`, `trace_id`, and `created_at`.
- `POST /sessions/{session_id}/plan` -> `list[PlanStepOut]` with no `patches` field.
- `POST /sessions/{session_id}/patches` -> `PatchProposalOut` with no `checks` field.
- `POST /patches/{patch_id}/check` -> five `GuardrailCheck` objects for R1-R5, including pass results.
- `GET /sessions/{session_id}` -> nested `Session` with `steps -> patches -> checks`.
