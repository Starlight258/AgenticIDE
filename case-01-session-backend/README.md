# [Case Title]

> One-line: what this service does, for whom.

## 1. Problem & Approach

- **What I built**: 1~2 sentence summary of the deliverable.
- **Why this approach**: 2~3 bullets — the design call I made and why.
- **Assumptions** (5+): each one I made when the spec was unclear.
- **Ambiguities I noticed**: 3+ — what I'd ask the PM if I had more time.

## 2. Domain Model

Core entities (with 1-line purpose):

- `Session` — ...
- `PlanStep` — ...
- `PatchProposal` — ...
- `GuardrailCheck` — ...

Relationship sketch:

```
Session 1—* PlanStep 1—* PatchProposal 1—* GuardrailCheck
```

## 3. AI Leverage

| Part | Done by | Verification |
|---|---|---|
| Domain models (pydantic) | Hand | Type-checked, tested |
| FastAPI endpoint scaffolding | AI (Claude Code) | Hand-reviewed diff |
| Guardrail rule parsing | AI | Pytest case |
| README structure | Hand | — |

**Verification mechanism**: every AI-generated patch went through pytest + manual diff scan. No AI output committed without a test.

## 4. Trade-offs & Decisions

- Chose X over Y because ...
- Skipped Z because the spec didn't justify it (would add in production).
- Known limitation: ...

## 5. If More Time

- Provider abstraction (e.g. LiteLLM) — currently Anthropic-only.
- Vertex AI deployment per brand region (efood→europe-west1, talabat→me-central1) for GDPR / data residency.
- Multi-brand rule override (efood/glovo/talabat).
- OTEL tracing on the guardrail check pipeline → DH OAM observability.
- Per-brand cost tracking → DH cost-center mapping.

## How to Run

```bash
uv sync
cp .env.example .env  # add your ANTHROPIC_API_KEY
uv run pytest
uv run uvicorn src.main:app --reload
```

## Tested Working

- `POST /sessions` → creates session
- `POST /sessions/{id}/plan` → AI generates plan steps
- `POST /patches/{id}/guardrail` → checks AGENTS.md violations
