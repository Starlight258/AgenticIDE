---
allowed-tools: Bash(git status:*), Bash(git branch:*), Bash(git diff:*), Bash(git log:*), Bash(git worktree:*), Bash(git merge:*), Bash(git add:*), Bash(git commit:*), Bash(uv run:*), Bash(curl:*), Bash(lsof:*), Bash(kill:*), Bash(pkill:*), Bash(rg:*), Bash(find:*), Bash(sed:*), Bash(grep:*), Bash(python3:*)
description: Execute the Agentic IDE take-home assignment playbook
---

Execute the Agentic IDE take-home assignment playbook.

## Context

- Current git status: !`git status --short`
- Current branch: !`git branch --show-current`
- Execution protocol: !`cat _shared/ASSIGNMENT_EXECUTION_PROTOCOL.md`
- Repository rules: !`cat _shared/AGENTS.md`

## Assignment Loading

`$ARGUMENTS` is the path to the assignment file (e.g. `/assignment case-01-session-second/assignment.md`).

- If `$ARGUMENTS` looks like a file path → read it: !`cat "$ARGUMENTS" 2>/dev/null || echo "⚠ File not found: $ARGUMENTS — paste assignment text below"`
- If `$ARGUMENTS` is empty → use default: !`cat case-01-session-backend/ASSIGNMENT.md 2>/dev/null || echo "⚠ No assignment file found. Re-run as: /assignment path/to/ASSIGNMENT.md"`

Whichever loads successfully is the authoritative assignment for this run.

## Your Task

1. Start with a todo list and keep it current.
2. Preserve the deterministic boundary: LLM proposes; schemas, routes, guardrails, and tests decide.
3. Keep P0/P1/P2 scope explicit. Do not add P2 features unless the user asks.
4. Use the Builder, Reviewer, and Tester agent definitions under `.claude/agents/` when delegating.
5. Never invent requirements. If the assignment is ambiguous, document the assumption in README.
6. Apply the **Production Hardening Tiers** from the protocol:
   Tier 1 is required before staging; Tier 2 should stay narrow unless explicitly requested.
7. Before declaring completion, run the **Phase 5 JD Alignment bash script** from the protocol —
   every `grep` and `python3` assertion must exit 0.
8. Before declaring completion, run the **Phase 6 Assignment Requirements Gate** from the protocol —
   read the loaded assignment, extract every endpoint/MUST/evaluation requirement, verify each one,
   and paste the full checkbox report. Every box must be `[x]` before submit.
9. Run the **format + lint gate** — both must be clean before commit:
   ```bash
   SRC=$([ -d src ] && echo src || echo app)
   uv run ruff format --check $SRC tests   # formatting gate — run `uv run ruff format $SRC tests` first if it fails
   uv run ruff check $SRC tests            # lint gate
   uv run pytest -v                        # test gate
   ```
   Also confirm no stray untracked files will be omitted from the submission:
   ```bash
   git status --short   # any ?? that should be staged or gitignored?
   ```
10. End with: files changed, pytest result, format + lint gate output, Phase 5 gate output, Phase 6 gate report.
11. **Phase 7 — Evaluator's Eye View**: after Phase 6 passes, run `/evaluate` on the submission:
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   cd "$REPO_ROOT/evaluator" && uv run evaluate --path "$REPO_ROOT/case-01-session-backend"
   ```
   Report total score, recommendation, and top 3 discussion questions.
   If any axis scores below 4, identify which phase should have caught the gap.

## Scoring Traps — check each before Phase 6

These are silent point-killers that look fine locally but fail the evaluator's first scan:

### 1. Spec endpoint must exist verbatim
The assignment specifies `POST /sessions/{id}/patches/{patchId}/check`. An evaluator checks this endpoint first.
- **Wrong**: `POST /patches/{patchId}/check` only — evaluator marks as missing, no partial credit
- **Right**: implement the spec endpoint with session ownership validation; keep the short form as an alias if desired
- Verify: `grep -r "sessions.*patches.*check" src/routes.py` must return a match

### 2. Sample diff must demonstrate R4/R5 BLOCK in E2E
The assignment provides a sample diff: `print(...)` violates R4, `requests.get(...)` violates R5.
- **Wrong**: mock diff that generates clean code — tests pass but prove nothing about the core requirement
- **Right**: mock diff matches the assignment sample diff; E2E test asserts `R4.result == "fail"` and `R5.result == "fail"` via `/check`
- Verify: at least one test name contains "r4" or "r5" and asserts `"BLOCK"` severity

### 3. AGENTS.md context must appear in BOTH prompts
The LLM "proposes within brand constraints" narrative only holds if the patch prompt also receives brand rules.
- **Wrong**: AGENTS.md in plan prompt only — patch LLM has no brand context
- **Right**: `_patch_prompt(step, brand)` reads AGENTS.md and includes it; `create_patch(step, brand)` signature reflects this
- Verify: `grep -n "agents" src/llm.py` shows AGENTS.md read in both plan and patch paths

### 4. Note the assignment self-contradiction in README
The assignment says `from .utils import calc` "passes R1" — but R1 requires absolute imports, and `from .utils` is a relative import. This is a contradiction.
- Document the decision: "We implement R1 as written in AGENTS.md (absolute imports required). The sample diff's `from .utils import calc` therefore fails R1 with WARN severity, contrary to the assignment's inline note."
- This shows you read carefully and made an explicit decision rather than being confused by it.

### 5. Session ownership validation on spec endpoint
`POST /sessions/{id}/patches/{patchId}/check` must verify the patch belongs to the session.
- A patch_id from session A used against session B must return 404
- This proves the endpoint is real, not just a URL alias

## Guardrails

- Do not post comments, open PRs, push, or alter remotes unless the user explicitly asks.
- Do not read `.entire/metadata/**`.
- Do not log, print, or commit secrets.
- Do not bypass `AGENTS.md`; brand rules must be loaded just-in-time where the protocol requires it.
