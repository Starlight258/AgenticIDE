# efood Engineering Manifesto

Rules enforced by the Agentic IDE guardrail for all AI-generated patches targeting the efood brand.

## R1 — Absolute imports only (syntactic)
All Python imports must be absolute. Relative imports (`from .module import ...`) are not permitted.

## R2 — No shell execution without review (security)
Direct calls to `os.system` or `subprocess` (any method) require explicit security review before merging. Flag any occurrence.

## R3 — Public functions must have docstrings (style)
Any public function (not prefixed with `_`) must include a docstring immediately after the `def` line.

## R4 — Use efood.logging, never print (brand)
Logging must use the `efood.logging` module. Direct `print()` calls are forbidden in production code.

## R5 — External HTTP via efood.http_client only (brand)
New external HTTP calls must go through `efood.http_client`. Direct use of `requests`, `httpx`, `urllib`, or similar libraries is not permitted.
