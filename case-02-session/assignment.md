From: agentic-ides-hiring@deliveryhero.com
Subject: Take-home — Agentic IDE Session Backend (Full, 4h)

Hi,

Thanks for sending the mini take-home. We'd like to see how you handle a
fuller version. Budget: 4 hours. GitHub repo when done.

──────────────────────────────────────────────────────────────────────
Background
──────────────────────────────────────────────────────────────────────
Same Agentic IDEs context as before — backends that host AI-assisted
coding sessions across Delivery Hero brands. This time the brand is
glovo, and glovo's engineering rules are stricter because their codebase
runs the courier marketplace where mistakes cost money.

We need the same Session → Plan → Patch → Check workflow, but glovo wants
two additional things on top of the mini version:

  (a) Multiple patches per PlanStep, with a "step readiness" verdict
      that aggregates guardrail results across all patches under that
      step.

  (b) A TestRun resource that records what happened when a reviewer
      "ran" the patches. Real test execution is out of scope; we want
      the data model and the API shape, plus a clear separation of what
      the LLM produced vs. what humans/automation recorded.

──────────────────────────────────────────────────────────────────────
Task
──────────────────────────────────────────────────────────────────────
Build an HTTP service for ONE brand: glovo. The service should:

1. POST   /sessions
2. POST   /sessions/{id}/plan
3. POST   /sessions/{id}/plan/{stepId}/patches      ← scoped to a step
4. POST   /sessions/{id}/patches/{patchId}/check
5. GET    /sessions/{id}/plan/{stepId}/readiness    ← aggregated verdict
6. POST   /sessions/{id}/test-runs                  ← record a TestRun
7. GET    /sessions/{id}                            ← full nested state

Endpoints 1–4 mirror the mini version. Endpoints 5–7 are new.

──────────────────────────────────────────────────────────────────────
Inputs we provide
──────────────────────────────────────────────────────────────────────

(A) glovo/AGENTS.md — five rules:
  G1. All money/price arithmetic must use `Decimal`, never `float`. (correctness)
  G2. No hardcoded external URLs — must come from `glovo.config`. (security)
  G3. Async DB access must use `glovo.db.session` context manager. (brand)
  G4. Public handlers must propagate `X-Glovo-Trace-Id` into structured logs. (observability)
  G5. Public functions must include a docstring with at least one `Args:` line. (style)

(B) Sample PR diff (sample_diff.patch):
  - Adds `payments/charge.py`:
    * `from decimal import Decimal` and `amount: Decimal` (passes G1)
    * `URL = "https://api.partner.com/charge"` hardcoded (VIOLATES G2)
    * `float(order.tip)` in same file (VIOLATES G1)
    * `async def charge(order):` no docstring (VIOLATES G5)
    * `async with engine.connect() as conn:` direct (VIOLATES G3)
    * trace_id not forwarded to logger (VIOLATES G4)

We expect at least G1, G2, G3, G4, G5 all to flag (5/5 fail), with
mixed severities decided by you.

──────────────────────────────────────────────────────────────────────
What we evaluate
──────────────────────────────────────────────────────────────────────
- Repo we can clone and run end-to-end in under a minute.
- README that explains decisions, trade-offs, and what you didn't do.
- A coherent answer for "step readiness" — is it ALL patches passing
  every BLOCK, or majority, or something else? Decide and defend.
- Any inconsistency between README claims and actual code costs points.
- AI usage is not a secret; tell us what you delegated and how you
  verified.

We do NOT specify: storage, auth, error model, async/sync, severity
ladder, how concurrent patches are handled, TestRun → patch linkage
shape, or how you mock the LLM. Decide and explain.

Good luck.