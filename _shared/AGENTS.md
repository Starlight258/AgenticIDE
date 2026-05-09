# Engineering Rules

> Loaded as context for any AI agent working in this repo.

## Security

- NEVER log, print, or commit raw API keys, tokens, or `.env` contents.
- Read all secrets via `os.getenv()` after `load_dotenv()`. Fail fast if missing.
- Reject any code that calls `eval`, `exec`, or `subprocess` with unsanitized input.

## Code Style

- All domain models = pydantic `BaseModel` subclasses with explicit type hints.
- Functions ≤ 30 lines. Split by intent, not by line count.
- No dead code, no TODO without a date, no commented-out blocks.
- `ruff check` and `ruff format` must pass before commit.

## Testing

- Every public function gets ≥ 1 pytest case.
- Tests use real types (no `Any`), no network calls (mock the LLM client).

## Assignment Protocol

When implementing an assignment or take-home case, read
`_shared/ASSIGNMENT_EXECUTION_PROTOCOL.md` before coding.

Apply its Production Hardening Tiers:
- Tier 1 is required before staging.
- Tier 2 should stay narrow unless explicitly requested.

## Multi-brand Awareness

- All entities carry a `brand` field: `"efood" | "glovo" | "talabat"`.
- Brand-specific rules override global rules. Default = global.

## AI Patch Validation (Guardrails)

Every AI-generated diff is validated against:

1. **Forbidden patterns** — `eval`, `exec`, hardcoded secrets, `os.system`.
2. **Type drift** — public function signatures cannot change without test update.
3. **Severity**: `BLOCK` (forbidden pattern) > `WARN` (style) > `INFO` (suggestion).

A patch with any `BLOCK` cannot be merged.

## Deployment Note

Production runs on Google Vertex AI (`AnthropicVertex` client) per region & brand.
Local dev uses the direct Anthropic API. Switch via the `USE_VERTEX=true` env var.
