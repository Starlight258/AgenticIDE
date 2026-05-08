# AgenticIDE — Claude Code Rules

## Commit Messages
- No `Co-Authored-By` line
- Format: `type: short description` (feat / fix / refactor / test / docs / chore)
- Message describes WHY, not what

## Workflow
- Use `/assignment <task>` for any new feature or assignment end-to-end
- Use `/think <decision>` before making any non-trivial design decision
- Use `/fastapi` constraints whenever touching Python FastAPI code
- Codex handles implementation (Phase 2 of /assignment); Claude handles design and review

## Code Rules (Python / FastAPI)
- Layer order: `api/` → `service/` → `crud/` — routes never import crud directly
- 3-tier schemas: `{Model}Create` (input) / `{Model}Out` (response) / SQLAlchemy model (DB)
- Pydantic v2: `ConfigDict(from_attributes=True)`, `model_dump()`, `model_validate()`
- No `HTTPException` inside `service/` — raise domain exceptions, handle in `main.py`
- `Annotated` aliases for all repeated `Depends()` — define in `api/deps.py`
- No `print()` anywhere — use `logging`
- LLM calls: always use `tool_use` + `tool_choice`, `max_tokens≥4096`, never `json.loads()` on raw response

## Test Rules
- Every response shape contract must have an assert: `assert "patches" not in response`
- E2E tests use file-based JSON parsing, not inline `python3 -c` pipe
- No mocking the DB in integration tests

## Before Every Push
```bash
uv run pytest -v       # 0 failed
uv run ruff check src/ # clean
```
README must match code — no false claims in architecture diagram.

## Repository Structure
```
AgenticIDE/
├── _shared/
│   ├── ASSIGNMENT_EXECUTION_PROTOCOL.md  # execution playbook
│   └── LESSONS_LEARNED.md               # post-mortem notes
└── case-01-session-backend/             # DH take-home assignment
    ├── src/
    │   ├── models.py    # 3-tier Pydantic schemas
    │   ├── routes.py    # FastAPI routes
    │   ├── llm.py       # Anthropic SDK (tool_use only)
    │   ├── guardrails.py # regex R1-R5, zero LLM calls
    │   └── store.py     # in-memory session store
    └── tests/
        ├── test_guardrails.py
        └── test_e2e.py
```
