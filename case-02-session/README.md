# case-02-session

Glovo-aware AI code review service for deciding whether an LLM-generated patch is safe to merge.

It is not a git apply or CI runner. It is the deterministic review layer between an agentic IDE and a developer's merge decision.

## Problem & Approach

Glovo developers currently read LLM-generated diffs, remember brand guardrails, and decide manually whether a patch is mergeable. This service turns that workflow into a stateful HTTP API:

- `POST /sessions` creates a review workspace.
- `POST /sessions/{id}/plan` asks the LLM to split work into steps.
- `POST /sessions/{id}/plan/{stepId}/patches` asks the LLM for one unified diff.
- `POST /sessions/{id}/patches/{patchId}/check` runs deterministic G1-G5 checks.
- `GET /sessions/{id}/plan/{stepId}/readiness` computes whether the latest patch can be considered merge-ready.
- `POST /sessions/{id}/test-runs` records human or CI test evidence.
- `GET /sessions/{id}` returns the nested session state.

The core architecture is a deterministic sandwich:

```text
Request
  -> deterministic session, brand, and AGENTS.md context
  -> LLM generates only PlanStepInput or PatchProposalInput
  -> Pydantic validates the LLM payload
  -> deterministic guardrails run from AGENTS.md severities
  -> deterministic readiness is computed from stored checks
```

The LLM proposes structure and diffs. The service owns validation, rule checks, readiness, audit state, ownership checks, idempotency, and test-run persistence.

Assumptions:

1. One session represents one developer's review workspace; cross-developer collaboration on the same patch is out of scope.
2. `brand="glovo"` is the evaluated path; `Brand` already allows `efood` and `talabat` for extension.
3. `AGENTS.md` is the runtime source of truth for rule severities, so guardrails read `glovo/AGENTS.md` when checks run.
4. Patches are proposals, not applied git changes; failed proposals remain history and a new patch can be generated.
5. `BLOCK` means not merge-ready, while `WARN` means review required but not an automatic readiness block.
6. `trace_id` is generated per session and stored for future OTEL/export integration.

## Domain Model

```text
Session 1 -> * PlanStep 1 -> * PatchProposal 1 -> * GuardrailCheck
Session 1 -> * TestRun
TestRun * -> * PatchProposal by patch_ids
StepReadiness is computed, not stored
```

- `Session`: the developer's review workspace, including `brand`, `owner_id`, `trace_id`, `steps`, and `test_runs`.
- `PlanStep`: one LLM-created implementation step with target files.
- `PatchProposal`: one LLM-created unified diff for a step, plus immutable check results and `version`.
- `GuardrailCheck`: deterministic result for one rule, including `ruleId`, `severity`, `result`, and `reason`.
- `TestRun`: reviewer or CI evidence for one or more patch IDs.

## Trust Boundaries

| Boundary | AI role | Deterministic code role |
|---|---|---|
| Planning | Splits title and description into steps | Loads session/brand context, validates `PlanStepInput`, enforces idempotency |
| Patch proposal | Produces a unified diff for one step | Stores proposal as a candidate; never applies it to the repo |
| Guardrails | No authority | Runs G1-G5 regex checks and reads severities from `glovo/AGENTS.md` |
| Readiness | No authority | Uses latest patch by `created_at`, stored checks, and BLOCK count |
| Test evidence | No authority | Stores reviewer or CI `TestRun` records as evidence, not as a readiness override |
| HTTP request | — | FastAPI/Pydantic validation plus ownership checks on all IDs |
| LLM output | Produces plan and diff text | Parsed with Pydantic DTOs before storage; raw text never trusted |
| Brand rules | — | Re-reads `glovo/AGENTS.md` at check time; ignores LLM claims about compliance |
| Mock mode | Returns deterministic sample plan and diff when no API key exists | Keeps quickstart and tests runnable without `.env` |

## Trade-offs

| Decision | Rationale | Reconsider if |
|---|---|---|
| Readiness uses the latest patch by `created_at` | Developers expect the newest patch to be the candidate; using an older checked patch could mark a step READY while the latest intended patch was never checked. | The API adds an explicit `intended_patch_id` or merge-candidate marker. |
| Patches are candidates, not applied changes | The service can review repeated AI attempts without mutating the real repository. | The product becomes a full merge bot with branch management. |
| Checks are stored once | A check is an audit event for one diff at one point in time, so readiness reads stored evidence instead of recomputing silently. | AGENTS.md changes must trigger explicit recomputation. |
| Optimistic lock via `version` | Contention is low because a session is a single developer workspace; CAS gives multi-worker safety without pessimistic lock overhead or Redis. | Patch mutation APIs or high-contention collaborative editing are added. |
| Second `POST /check` returns 409 | POST creates a check event; if checks already exist, the second request conflicts with the existing event but returns the prior checks in the body. | The product wants `/check` to be a cache lookup instead of an event creation endpoint. |
| Guardrails are regex-based | G1-G5 are concrete policy patterns that should be explainable and repeatable. | Rules require semantic code understanding across files. |

### Decision 2: Readiness

Readiness intentionally uses the most recent patch by `created_at`, even if it has not been checked yet. That prevents a stale clean patch from hiding a newer unchecked patch that the developer actually intends to merge.

`NOT_READY` means one of three things:

1. No patches exist for the step.
2. The latest patch exists but has not been checked.
3. The latest patch has at least one failed `BLOCK` check.

Warnings do not block readiness because they represent review attention, not automatic merge rejection.

### Decision 7: Optimistic Locking

`PatchProposal.version` and `update_patch_if_version` implement compare-and-set around check creation. This fits the workload because the realistic race is a same-user double click or two tabs, not many developers competing for one shared counter.

The SQLite implementation updates only when `PatchProposalRow.version == expected_version`, then increments the version and stores checks in the same operation. That remains safe across workers sharing one database, while avoiding the cost and complexity of Redis or pessimistic row locks for a low-contention path.

### Decision 8: 409 Conflict

`POST /check` creates a check event. Calling it again for the same patch conflicts with the stored event, so the service returns `409 checks_already_exist` with the existing checks included instead of silently pretending a new check was created.

## Error Model

| Case | Status | Error |
|---|---:|---|
| Missing session path ID | 404 | `session_not_found` |
| Missing step path ID | 404 | `step_not_found` |
| Missing patch path ID | 404 | `patch_not_found` |
| Patch from another session in check path | 404 | `patch_not_found` |
| TestRun body references unknown patch | 422 | `patch_not_found_in_payload` |
| TestRun body references another session's patch | 422 | `patch_not_in_session` |
| Duplicate `POST /check` | 409 | `checks_already_exist` |
| Optimistic lock race | 409 | `version_conflict` |

Path IDs use 404 because the addressed resource is unavailable in that URL. Body IDs use 422 when the JSON is syntactically valid but violates session semantics.

## Implementation Signals

- `src/guardrails.py` reads `{brand}/AGENTS.md` at check time and falls back to built-in severities if the file is missing.
- `PatchProposal.version` exists and `SessionRepository.update_patch_if_version` is used by `service._run_patch_checks`.
- `src/llm.py` uses Anthropic tool calling with `tool_choice={"type": "tool", "name": "output"}` and does not parse LLM text with `json.loads`.
- `PlanStepOut` excludes `patches`; `PatchProposalOut` excludes `checks`, so response shapes reflect the workflow stage.
- `glovo/sample_diff.patch` is the mock patch, so the default demo triggers G1-G5 without external credentials.

## If More Time

- **SQLite hardening**: add migrations, indexes for session/step/patch lookups, and a documented cleanup policy for old sessions.
- **OTEL**: export `trace_id`, LLM latency, guardrail outcomes, and readiness transitions as spans and metrics.
- **Multi-brand**: add brand-specific rule modules and AGENTS.md fixtures for `efood` and `talabat`, while keeping the same API shape.
- **LLM-as-judge**: add an advisory semantic review layer after deterministic checks, but never let it override BLOCK rules directly.
- **Explicit recompute**: add `POST /patches/{id}/checks/recompute` or delete-then-check semantics when AGENTS.md changes.

## How to Run

No `.env` file is required. If `ANTHROPIC_API_KEY` is absent, the app automatically uses the built-in mock plan and mock patch. If the key is present, `src/llm.py` calls the configured Anthropic model.

```bash
uv sync
uv run pytest
uv run fastapi dev src/main.py
```

Open:

```text
http://localhost:8000/docs
```

Healthcheck:

```bash
curl -s localhost:8000/health
```

Minimal glovo workflow:

```bash
SESSION_ID=$(curl -s -X POST localhost:8000/sessions \
  -H "Authorization: Bearer demo" \
  -H "Content-Type: application/json" \
  -d '{"title":"Charge endpoint","description":"Add charge handler","brand":"glovo"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

STEP_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/plan \
  -H "Authorization: Bearer demo" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

PATCH_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/plan/$STEP_ID/patches \
  -H "Authorization: Bearer demo" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST localhost:8000/sessions/$SESSION_ID/patches/$PATCH_ID/check \
  -H "Authorization: Bearer demo" \
  | python3 -m json.tool

curl -s localhost:8000/sessions/$SESSION_ID/plan/$STEP_ID/readiness \
  -H "Authorization: Bearer demo" \
  | python3 -m json.tool
```

Expected mock behavior for `brand="glovo"`: the sample patch fails G1, G2, G3, G4, and G5, so readiness is `NOT_READY`.
