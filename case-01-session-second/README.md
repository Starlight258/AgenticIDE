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
[Rate limiter — slowapi]                                                  <- deterministic

[Bearer auth — HTTPBearer]
  reject if Authorization header is missing or empty -> 403              <- deterministic

[POST /sessions]
  create Session with server-side id, trace_id, owner_id, created_at, steps=[]  <- deterministic
  persist to SQLite                                                       <- deterministic

[POST /sessions/{session_id}/plan]
  load Session from SQLite, verify owner_id == actor -> 403 if mismatch  <- deterministic
  Idempotency-Key header hit? return cached response                      <- deterministic
  -> Claude tool_use output: list of plan steps                           <- non-deterministic, schema-constrained
  -> Pydantic validates PlanStepInput, SQLite saves PlanStep objects      <- deterministic
  -> log audit record (trace_id, actor, action)                           <- deterministic
  -> store idempotency key if header present                              <- deterministic

[POST /sessions/{session_id}/patches]
  load Session from SQLite, verify owner_id == actor -> 403 if mismatch  <- deterministic
  Idempotency-Key header hit? return cached response                      <- deterministic
  -> Claude tool_use output: unified diff (tenacity retry, max 3 attempts) <- non-deterministic, schema-constrained
  -> Pydantic validates PatchProposalInput, SQLite saves PatchProposal    <- deterministic
  -> log audit record                                                      <- deterministic

[POST /sessions/{session_id}/patches/{patch_id}/check]  (spec endpoint)
  load Session from SQLite, verify owner_id == actor -> 403 if mismatch  <- deterministic
  verify patch belongs to session -> 404 if not                           <- deterministic
  load PatchProposal, inspect added diff lines with R1-R5 regex           <- deterministic
  -> SQLite overwrites checks on each call                                <- deterministic

[POST /patches/{patch_id}/check]  (alias — patch UUID is globally unique)
  verify actor owns the session that contains the patch -> 403 if not    <- deterministic
  same guardrail evaluation as spec endpoint

[GET /sessions/{session_id}]
  load Session from SQLite, verify owner_id == actor -> 403 if mismatch  <- deterministic
  -> full state: Session -> steps -> patches -> checks
```

The LLM proposes work; deterministic Python decides whether the proposed patch passes, warns, or blocks under R1-R5.

**Actual endpoints**:

| Method | Path | Response model | Notes |
|--------|------|----------------|-------|
| `GET` | `/health` | `dict[str, str]` | |
| `POST` | `/sessions` | `Session` | |
| `POST` | `/sessions/{session_id}/plan` | `list[PlanStepOut]` | no `patches` field |
| `POST` | `/sessions/{session_id}/patches` | `PatchProposalOut` | no `checks` field |
| `POST` | `/sessions/{session_id}/patches/{patch_id}/check` | `list[GuardrailCheck]` | **spec endpoint** — validates ownership |
| `POST` | `/patches/{patch_id}/check` | `list[GuardrailCheck]` | alias — patch UUID is globally unique |
| `GET` | `/sessions/{session_id}` | `Session` | full nested state |

**Assumptions**:
1. Storage is SQLite (`sessions.db`) via SQLAlchemy async (`src/sqlite_repository.py`). Sessions persist across process restarts. The file `src/store.py` is an unused in-memory reference implementation.
2. efood policy lives in `efood/AGENTS.md` and is implemented as regex checks in `src/guardrails.py`.
3. `BLOCK` means a merge gate must fail, `WARN` means reviewer attention is required, and `INFO` is available in the schema but not currently emitted by R1-R5.
4. LLM output is accepted only through Anthropic `tool_use` and Pydantic validation; domain models are not passed to the LLM.
5. `brand` accepts `efood`, `glovo`, or `talabat` at the schema layer, but only the efood rules are implemented.
6. `trace_id` is generated and returned on `Session`; there is no OTEL or distributed tracing.
7. If `ANTHROPIC_API_KEY` is absent, `src/llm.py` returns a deterministic mock plan and a mock patch that matches the assignment's sample diff (`from .utils import calc`, `print(...)`, `requests.get(...)`) — this lets local runs and tests demonstrate R4 and R5 blocking without a live API key.
8. All routes except `/health` require a Bearer token (`Authorization: Bearer <token>`). Any non-empty token is accepted as the actor identity; session and patch operations are scoped to that actor.
9. `Idempotency-Key` header is supported on `POST /sessions/{id}/plan` and `POST /sessions/{id}/patches`; repeated requests with the same key return the cached response without re-calling the LLM.
10. LLM calls use tenacity retry (up to 3 attempts, exponential back-off) on `APIStatusError`. If the API is unreachable after retries, `LLMUnavailableError` is raised and mapped to `503`.

**Ambiguities I noticed**:
1. The schema accepts `glovo` and `talabat`, but the spec says not to build multi-brand routing; this implementation stores the brand and applies the same efood guardrails.
2. R3 defines "public function without docstring" for added lines only; this implementation checks whether the next non-empty added line after `def name(...)` starts with a triple-quoted docstring.
3. The service returns guardrail checks, not a separate merge decision object; downstream callers must interpret any `BLOCK` failure as not mergeable.
4. **R1 contradiction in the sample diff**: the assignment states that `from .utils import calc` "passes R1", but R1 requires absolute imports and `from .utils` is a relative import. This implementation applies R1 as written in `efood/AGENTS.md` — the sample diff's relative import therefore fails R1 with `WARN` severity. The assignment's inline note appears to be an error in the spec.

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
Scope checks under sessions; session ownership is validated server-side.
Risk: callers must carry both IDs, but both are available from the workflow.

**Option 2 - `/patches/{patch_id}/check`**
Check by globally unique patch ID.
Risk: the URL does not visibly show the parent session; no ownership validation.

**Option 3 - Compute checks during patch creation**
Always run guardrails inside `POST /sessions/{session_id}/patches`.
Risk: callers cannot explicitly re-run checks, and idempotent overwrite behavior is harder to demonstrate.

**I chose Option 1** as the primary endpoint because it matches the assignment spec verbatim, allows session ownership validation (patch from session A is rejected when requested under session B), and makes the resource hierarchy explicit. Option 2 is retained as an alias because patch UUIDs are globally unique and the short form is convenient for direct patch lookups. The trade-off is that callers must carry both IDs for the spec path, which is acceptable in a session-scoped workflow.

---

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| SQLite storage via SQLAlchemy async | Durable across restarts without introducing a separate DB process; simple async driver (`aiosqlite`). | Multiple workers need shared state or sessions grow beyond SQLite's write concurrency. |
| Deterministic regex guardrails | R1-R5 are explicit string patterns, so deterministic checks are more reliable than LLM review. | Rules require Python AST analysis, dataflow, or repo-wide context. |
| LLM only for plan and patch generation | Keeps creative generation separate from merge policy. | The product needs natural-language explanation after deterministic checks complete. |
| Spec endpoint + alias for check | Spec endpoint validates session ownership; alias validates patch ownership via the actor's token. Patch UUIDs are globally unique. | Patch IDs become scoped or ownership validation needs stricter access control. |
| Store all five check results | Callers can see pass and fail outcomes for every R1-R5 rule. | Payload size becomes an issue after adding many more rules. |
| Idempotent check overwrite | Re-running `/check` replaces prior checks for the same patch. | Historical guardrail runs need audit retention. |
| Bearer token auth — any non-empty token accepted | Satisfies session-ownership scoping without requiring a full identity provider. The actor is the raw token string. | The API is exposed outside trusted environments or needs real identity verification. |
| Idempotency-Key header | Prevents duplicate LLM calls if the client retries after a timeout. | Fine-grained per-user or per-resource idempotency windows are needed. |
| tenacity retry on LLM calls | Transient `APIStatusError` failures (rate limit, 5xx) are retried automatically before surfacing as `503`. | Retry budget must be caller-controlled or capped by request deadline. |
| Rate limiting via slowapi | Prevents unbounded LLM call storms at the API layer. | Per-actor or per-tier limits are needed instead of flat IP-based limits. |
| structlog structured logging + audit table | Provides trace_id/actor context on every log line; audit table records create_plan and create_patch actions. | Logs must flow to an external sink (OTEL, Datadog). |
| No multi-brand routing | `brand` is stored, but only efood rules are implemented. | Glovo or talabat require different rule files or severity policies. |
| No async queue or streaming LLM | Requests are synchronous and simple to test. | Patch generation becomes slow or needs progress updates. |
| No OTEL or distributed tracing | Only a `trace_id` field exists today. | The service participates in production request tracing. |
| Direct Anthropic SDK with `tool_use` | It directly satisfies `tool_choice={"type":"tool","name":"output"}` and `max_tokens=4096`. | Multiple providers or richer orchestration become required. |

---

## 5. Edge Cases Considered

- Missing session ID returns `404`.
- Missing step ID inside an existing session returns `404`.
- Missing patch ID returns `404` on both spec and alias endpoints.
- Patch from session A used on session B's spec endpoint returns `404` (session ownership validation).
- `/check` can be called repeatedly and overwrites prior checks (idempotent).
- Unknown `brand` values fail at Pydantic request validation with `422`.
- Missing `ANTHROPIC_API_KEY` uses deterministic mock LLM output (sample diff with R4/R5 violations).
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

| Part | Verification |
|------|--------------|
| `pyproject.toml` | Dependency/import validation through `uv run pytest`; style through `uv run ruff check`. |
| `src/main.py` | `GET /health` test and route import through FastAPI `TestClient`; lifespan creates SQLite tables; rate limiter and exception handlers registered. |
| `src/config.py` | `Settings` reads `ANTHROPIC_API_KEY`, `db_url`, `model` from environment; validated via pydantic-settings. |
| `src/auth.py` | HTTPBearer dependency; any non-empty token accepted as actor. Tested via auth-required routes in `tests/test_e2e.py`. |
| `src/guards.py` | `get_owned_session` and `verify_patch_ownership` enforce actor ownership; `OwnershipError` raised on mismatch. |
| `src/models.py` | Domain models including `owner_id` on `Session`; response-shape tests in `tests/test_e2e.py`. |
| `src/schemas.py` | Input and output schemas (SessionCreate, PlanStepOut, PatchProposalOut, etc.); field exclusions verified by response-shape tests. |
| `src/repository.py` | `SessionRepository` Protocol; `log_audit` and `set_idempotency` / `get_idempotency` included in contract. |
| `src/sqlite_repository.py` | SQLAlchemy async implementation of all repository methods including audit and idempotency. |
| `src/db.py` | `create_tables` and `get_session` async generator; used by lifespan and `deps.py`. |
| `src/db_models.py` | SQLAlchemy ORM table definitions. |
| `src/deps.py` | `RepoDepend`, `LLMDepend`, `IdemDepend` annotated aliases; idempotency cache read from SQLite. |
| `src/errors.py` | `NotFoundError`, `OwnershipError` domain exceptions. |
| `src/exceptions.py` | FastAPI exception handlers mapping domain errors to HTTP status codes. |
| `src/routes.py` | Spec endpoint + alias; ownership via guards; idempotency cache; audit log calls; endpoint coverage in `tests/test_e2e.py`; README URLs grepped from decorators. |
| `src/service.py` | Full session workflow, ownership check, 404 behavior, and check overwrite tests. |
| `src/llm.py` | Mock returns sample diff (R4/R5 violations); patch prompt includes AGENTS.md brand context; tenacity retry on `APIStatusError`; `LLMUnavailableError` on exhausted retries. |
| `src/guardrails.py` | R1-R5 unit tests in `tests/test_guardrails.py`. |
| `src/logging_config.py` | structlog configuration; context vars bound per request (actor, session_id, trace_id). |
| `src/store.py` | In-memory reference implementation; not wired into the request path (replaced by `SQLiteRepository`). |
| `tests/conftest.py` | In-memory repository injected via DI override; LLM patched with `unittest.mock.patch`. |
| `tests/test_guardrails.py` | Exercises empty patch, added-line filtering, and each R1-R5 rule. |
| `tests/test_e2e.py` | Exercises health, auth rejection, spec endpoint, R4/R5 BLOCK demo, session ownership rejection, response shapes, validation, 404s, idempotent checks, and alias endpoint. |
| `efood/AGENTS.md` | Rule text cross-checked against `src/guardrails.py` and tests. |
| `README.md` | Cross-checked against route decorators, models, tests, and spec exclusions. |

---

## 7. If More Time

- **Authentication and authorization** -> Bearer token auth and session/patch ownership are implemented. The next step is a real identity provider (e.g. JWT validation) to replace the accept-any-token approach.
- **Persistence with DB or Redis** -> SQLite is already in place. The next step is migrating to PostgreSQL (or adding Redis for caching) when multiple workers or horizontal scaling are needed.
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

# SQLite database is created automatically at ./sessions.db on first startup.
```

Healthcheck:

```bash
curl localhost:8000/health
# {"status":"ok"}
```

Full workflow:

```bash
# All endpoints except /health require a Bearer token. Any non-empty string works.
TOKEN="my-dev-token"
AUTH="-H \"Authorization: Bearer $TOKEN\""

# 1. Create a session.
SESSION_ID=$(curl -s -X POST localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"AI coding session","description":"Implement deterministic efood guardrails","brand":"efood"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. Create plan steps for the session.
STEP_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/plan \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. Create a patch for one step.
PATCH_ID=$(curl -s -X POST localhost:8000/sessions/$SESSION_ID/patches \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"step_id\":\"$STEP_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 4. Run deterministic guardrails (spec endpoint — validates patch belongs to session).
curl -s -X POST localhost:8000/sessions/$SESSION_ID/patches/$PATCH_ID/check \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# Expected: R4 fail/BLOCK (print), R5 fail/BLOCK (requests.get), R1 fail/WARN (relative import)

# 5. Read full nested session state.
curl -s localhost:8000/sessions/$SESSION_ID \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

## Tested Working

- `GET /health` -> `{"status":"ok"}` (no auth required).
- Missing or empty `Authorization` header on any other endpoint -> `403`.
- `POST /sessions` -> `Session` with `steps=[]`, server-generated `id`, `trace_id`, `owner_id`, and `created_at`; persisted to SQLite.
- `POST /sessions/{session_id}/plan` -> `list[PlanStepOut]` with no `patches` field; repeated call with same `Idempotency-Key` returns cached result.
- `POST /sessions/{session_id}/patches` -> `PatchProposalOut` with no `checks` field; repeated call with same `Idempotency-Key` returns cached result.
- `POST /sessions/{session_id}/patches/{patch_id}/check` -> five `GuardrailCheck` objects; R4=fail/BLOCK and R5=fail/BLOCK on mock sample diff.
- `POST /patches/{patch_id}/check` -> same guardrail result; alias validates actor owns the patch's parent session.
- Spec endpoint with patch from a different session -> `404`.
- Accessing another actor's session -> `403`.
- `GET /sessions/{session_id}` -> nested `Session` with `steps -> patches -> checks`.
