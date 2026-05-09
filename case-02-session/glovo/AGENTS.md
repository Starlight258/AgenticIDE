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
- `ruff check` and `ruff format` must pass before commit.
