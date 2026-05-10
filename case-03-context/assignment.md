From: agentic-ides-hiring@deliveryhero.com
Subject: Take-home — DH Context Injection Server (Mini, 2h)

Hi,

Thanks for the take-home so far. Here's a smaller follow-up exercise
focused on a different slice of the team's work — context injection.
Budget: 2 hours. GitHub repo when done.

──────────────────────────────────────────────────────────────────────
Background
──────────────────────────────────────────────────────────────────────
Our Agentic IDEs team builds an integration layer that turns a general
IDE (Cursor, Claude Code) into a DH-aware coding system. Part of that
layer exposes internal context — PR history, Slack threads, GDrive docs
— as tools the LLM can call inside the IDE.

The IDE's LLM does NOT live in your service. Your service is the
context provider — it defines tools, runs them with brand-aware
permissions, and records who called what. The LLM is the client.

──────────────────────────────────────────────────────────────────────
Task
──────────────────────────────────────────────────────────────────────
Build an HTTP service (FastAPI) that exposes 3 tools, each callable by
an LLM client. The service should:

1. GET /tools
   - Return the tool catalog: name, description, input schema (JSON
     schema), brand requirements.

2. POST /tools/{name}/invoke
   - Run a tool with given arguments. Validate args against the tool's
     input schema. Apply brand permission. Return the tool result plus
     a tool_call_id (for audit).

3. GET /audit
   - Return the recent tool-call log: who, what, when, brand, result
     summary, latency. For a reviewer to see "did the LLM ever call
     anything it shouldn't have?".

──────────────────────────────────────────────────────────────────────
Tools to expose (mock the backends — no real APIs)
──────────────────────────────────────────────────────────────────────

(A) search_prs
Args: { query: string, brand: enum(efood,glovo,talabat), limit: int }
Returns: list of { pr_id, title, author, status, brand }
Brand permission: caller's brand must equal the searched brand
(no cross-brand PR search).

(B) get_slack_messages
Args: { channel: string, since: iso8601, brand: enum(...) }
Returns: list of { ts, author, text, channel, brand }
Brand permission: caller can only read channels in their brand's
whitelist (provide a small whitelist per brand).

(C) fetch_gdrive_doc
Args: { doc_id: string, brand: enum(...) }
Returns: { doc_id, title, content, brand, last_modified }
Brand permission: caller's brand must match doc's brand.

──────────────────────────────────────────────────────────────────────
Caller identity
──────────────────────────────────────────────────────────────────────
Every request includes header `X-Caller-Brand: efood|glovo|talabat`.
That's the caller's brand for permission checks. (Real auth is out
of scope for this task.)

──────────────────────────────────────────────────────────────────────
What we evaluate
──────────────────────────────────────────────────────────────────────

- A working repo (`how-to-run` in under a minute).
- A README explaining your tool schema design, permission model, and
  what's deliberately mocked.
- Audit trail: enough info to answer "what did the LLM call, with
  what args, and was it allowed?" — without exposing secrets.
- AI usage: tell us what you delegated to AI to build this and how
  you verified.

We do NOT specify: storage (in-memory OK), schema format (Pydantic vs
hand-rolled JSON Schema), error model, async vs sync, audit retention,
how to mock the backends, or whether to use FastMCP / build directly
on FastAPI. Decide and explain.

Good luck.
