# AgenticIDE — Project Context

## Workflow
- `/assignment <task>` — end-to-end: design → Codex implement → README polish → gate
- `/think <decision>` — before any non-trivial design decision
- `/fastapi` — FastAPI best practices reference

## Repository Structure
```
AgenticIDE/
├── _shared/
│   ├── ASSIGNMENT_EXECUTION_PROTOCOL.md  # execution playbook for take-home assignments
│   └── LESSONS_LEARNED.md               # post-mortem notes
└── case-01-session-backend/             # DH Agentic IDEs IC1 take-home
    ├── src/
    │   ├── models.py      # 3-tier Pydantic schemas
    │   ├── routes.py      # FastAPI routes (api/ → service/ → crud/ pattern)
    │   ├── llm.py         # Anthropic SDK — tool_use only
    │   ├── guardrails.py  # deterministic regex R1–R5, zero LLM calls
    │   └── store.py       # in-memory session store
    └── tests/
        ├── test_guardrails.py
        └── test_e2e.py
```

## Code and commit rules live in ~/.claude/rules/
- `python-fastapi.md` — applies to all *.py files
- `tests.md` — applies to test_*.py files
- `commits.md` — applies globally
