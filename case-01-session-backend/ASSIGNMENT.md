From: agentic-ides-hiring@deliveryhero.com
Subject: Take-home — Agentic IDE Session Backend (Mini)

Hi,

Thanks for moving forward with us. Below is a scoped technical exercise.
Budget: 90 minutes (we usually run a 4-hour version; this is a compressed
take-home for early-stage screening). Please send a GitHub repo link when done.

──────────────────────────────────────────────────────────────────────
Background
──────────────────────────────────────────────────────────────────────
Our Agentic IDEs team is building backends that power AI-assisted coding
sessions across Delivery Hero's brands (efood, Glovo, Talabat, foodora,
foodpanda). Each brand maintains its own AGENTS.md — an "Engineering
Manifesto" that codifies what AI-generated code is allowed to look like.

We need a backend service that hosts these sessions: a developer asks for
a change, the LLM proposes a patch, our guardrails decide whether the
patch is safe to merge against the brand's AGENTS.md rules.

──────────────────────────────────────────────────────────────────────
Task
──────────────────────────────────────────────────────────────────────
Build an HTTP service that exposes the following workflow for ONE brand:
efood. The service should:

1. POST /sessions
   - Create a session for a developer request (title, description, brand).

2. POST /sessions/{id}/plan
   - Given the session description, return a list of PlanStep
     (description + target files). The LLM proposes; you decide the
     contract.

3. POST /sessions/{id}/patches
   - Given a PlanStep, return a PatchProposal (a unified diff string).
     The LLM proposes; you decide the contract.

4. POST /sessions/{id}/patches/{patchId}/check
   - Run guardrails against the patch. Return a list of GuardrailCheck
     (ruleId, severity, result, reason). Guardrails MUST consult the
     brand's AGENTS.md.

5. GET /sessions/{id}
   - Return the full session state for a reviewing engineer.

──────────────────────────────────────────────────────────────────────
Inputs we provide
──────────────────────────────────────────────────────────────────────

(A) efood/AGENTS.md — five rules:
R1. All Python imports must be absolute. (syntactic)
R2. No direct calls to `os.system` or `subprocess` without explicit
review. (security)
R3. Public functions must have docstrings. (style)
R4. Logging must use the `efood.logging` module — never `print`. (brand)
R5. New external HTTP calls must go through `efood.http_client`. (brand)

(B) Sample PR diff to test against (sample_diff.patch):

- Adds a new module `pricing/discount.py` with:
  - `from .utils import calc` (passes R1)
  - `def apply_discount(order, pct):` with docstring (passes R3)
  - `print(f"Discount applied: {pct}")` (VIOLATES R4)
  - `requests.get(provider_url)` (VIOLATES R5)

We expect at least R4 and R5 to flag.

──────────────────────────────────────────────────────────────────────
What we evaluate
──────────────────────────────────────────────────────────────────────

- A working repo (`how-to-run` in under a minute).
- A README that explains decisions, trade-offs, and what you didn't do.
- Code we can read on a phone screen — we don't grade line count.
- How you used AI to build this is part of the evaluation, not a secret.

We do NOT specify: storage, auth, error model, async vs. sync, how
strictly to enforce rules, what "severity" means, or how to mock the
LLM. Decide and explain.

Good luck.
