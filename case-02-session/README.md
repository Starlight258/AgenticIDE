# [Case Title]

> [One line: what this service does and for whom — "DH-aware X that does Y before Z"]
>
> [Second line: what it is NOT — "It is not a clone of X — it is the layer that…"]

---

## 1. Problem & Approach

**What this replaces**: [the manual workflow this service eliminates — start with developer pain]

**Architecture**:

```
[Request]
    │
    ▼
[POST /X]
  [deterministic input setup]                  ← deterministic

[POST /X/{id}/Y]
  [context loaded just-in-time]                ← deterministic
  → LLM([model]): [what LLM does]             ← non-deterministic, schema-constrained
  → [output validation]                        ← deterministic

[POST /X/{id}/Z]
  → [deterministic check]                      ← deterministic
  → [gate decision]                            ← deterministic

[GET /X/{id}]
  → full state: [what's nested]
```

[One sentence: what the LLM does vs what deterministic code decides.]

**Assumptions**:
1. [storage scope] — [swap path if requirement changes]
2. [context source] — [who owns it, how it's loaded]
3. [severity semantics] — [what BLOCK/WARN/INFO means for merge]
4. [LLM output contract] — [how output is validated before storage]
5. [brand/tenant scope] — [what's currently supported vs extension path]
6. [observability] — [what trace_id / logging covers now]
7. [mock mode] — [what happens without real credentials]

**Ambiguities I noticed**:
1. [question 1 — what's unclear from the spec]
2. [question 2]
3. [question 3 — what you'd ask PM if you had more time]

---

## 2. Domain Model

- `[Entity1]` — [one-line purpose]
- `[Entity2]` — [one-line purpose]
- `[Entity3]` — [one-line purpose]
- `[Entity4]` — [one-line purpose]

```
[Entity1] 1—* [Entity2] 1—* [Entity3] 1—* [Entity4]
```

[Severity or status ladder if applicable]: `[HIGH]` > `[MED]` > `[LOW]`.
[One sentence on what the output feeds downstream — KPI, dashboard, metric.]

---

## 3. Key Design Decisions

The hardest part of this problem was [X]. I considered three options:

### [Core hard problem — e.g. concurrency control / guardrail enforcement / consistency]

**Option 1 — [name]**
[one sentence on how it works]
Risk: [what breaks under this approach]

**Option 2 — [name]**
[one sentence on how it works]
Risk: [what breaks under this approach]

**Option 3 — [name]**
[one sentence on how it works]
Risk: [what breaks under this approach]

**I chose Option [N]** because [correctness / simplicity / scope fit].
The trade-off is [X], which is acceptable because [Y].
I would reconsider if [Z].

### [Second significant decision if applicable]

[Same format — options considered, choice made, trade-off acknowledged]

---

## 4. Trade-offs & Decisions

| Decision | Rationale | Reconsider if |
|----------|-----------|---------------|
| [storage choice] | [why — what it removes from critical path] | [when to swap] |
| [deterministic vs LLM for X] | [why deterministic wins here] | [when LLM would be right] |
| [scope cut] | [why this wasn't needed for spec] | [when to add it] |
| [no auth] | [why out of scope] | [when staging/prod changes this] |
| [SDK choice] | [why direct over framework] | [when to reconsider] |
| [parallel worktrees] | [what was independent, what the benefit was] | [when branches diverge too much] |

---

## 5. Edge Cases Considered

- [primary race condition — e.g. two requests hitting same resource simultaneously]
- [same-user duplicate request — idempotency]
- [boundary overflow — e.g. capacity going negative]
- [cascade effect — deleting X while Y is in progress]
- [constraint interaction — e.g. credit limit + concurrent enrollment]
- [config change during active operation — e.g. capacity modified mid-session]

For [most critical case]: [one sentence on how the implementation handles it, or why it's explicitly out of scope with documented assumption].

---

## 6. AI Usage Log

I used AI as a reasoning partner, not only as a code generator.

Example prompts I used during design:
- "[question about failure modes — e.g. What race conditions can happen in X?]"
- "[question that challenged my initial approach — e.g. Is Y-level locking enough if Z?]"
- "[comparison prompt — e.g. Compare approach A and B for high-contention X]"
- "[review prompt — e.g. Review my design for missing consistency issues]"

Every AI-generated file went through: `ruff check` → `uv run pytest` → manual diff scan.
No AI output was committed without a test covering the specific behavior.

The final decisions were reviewed and adjusted by me before implementation.
I made the final design choices by comparing correctness, complexity, and assignment scope.

| Part | Verification |
|------|--------------|
| Domain models | Type-checked by Pydantic |
| [File/component] | [how it was verified] |
| [File/component] | [how it was verified] |
| README | Cross-checked against route decorators, models, and tests |

---

## 7. If More Time

- **[Feature 1]** → [one sentence on what it enables]
- **[Feature 2]** → [one sentence]
- **[Feature 3]** → [one sentence — show extension path is already designed in schema]
- **[Observability]** → push `trace_id` spans to [monitoring system]; ties into [KPI]
- **[Multi-tenant]** → `[field]` already in schema; add `[config file]` per tenant — no route changes needed

---

## How to Run

```bash
uv sync
cp .env.example .env          # set [API_KEY_VAR] (or leave blank for mock mode)
uv run pytest                 # all tests green
uv run uvicorn src.main:app --reload
# → http://localhost:8000/docs
```

Healthcheck:
```bash
curl localhost:8000/health
# {"status":"ok"}
```

Full workflow:

```bash
# 1. [first step]
RESOURCE=$(curl -s -X POST localhost:8000/[endpoint] \
  -H "Content-Type: application/json" \
  -d '[payload]' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. [second step]
SUB=$(curl -s -X POST localhost:8000/[endpoint]/$RESOURCE/[sub] \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. [key step — the one that demonstrates the core behavior]
curl -s -X POST localhost:8000/[endpoint]/$RESOURCE/[check] \
  | python3 -m json.tool

# 4. full state
curl -s localhost:8000/[endpoint]/$RESOURCE | python3 -m json.tool
```

## Tested Working

- `GET /health` → `{"status": "ok"}`
- `POST /[create]` → [what it returns]
- `POST /[core action]` → [what it demonstrates — the main feature]
- `POST /[check/guardrail]` → [what violations look like]
- `GET /[full state]` → [nested structure confirmed]
