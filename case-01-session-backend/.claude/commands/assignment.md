---
allowed-tools: Bash(git status:*), Bash(git branch:*), Bash(git diff:*), Bash(git log:*), Bash(git worktree:*), Bash(git merge:*), Bash(git add:*), Bash(git commit:*), Bash(uv run:*), Bash(curl:*), Bash(lsof:*), Bash(kill:*), Bash(pkill:*), Bash(rg:*), Bash(find:*), Bash(sed:*), Bash(grep:*), Bash(python3:*)
description: Execute the Agentic IDE take-home assignment playbook
---

Execute the Agentic IDE take-home assignment playbook.

## Context

- Current git status: !`git status --short`
- Current branch: !`git branch --show-current`
- Execution protocol: !`cat ../_shared/ASSIGNMENT_EXECUTION_PROTOCOL.md`
- Repository rules: !`cat ../_shared/AGENTS.md`

## Assignment Loading

`$ARGUMENTS` is the path to the assignment file (e.g. `/assignment ASSIGNMENT.md`).

- If `$ARGUMENTS` looks like a file path → read it: !`cat "$ARGUMENTS" 2>/dev/null || echo "⚠ File not found: $ARGUMENTS — paste assignment text below"`
- If `$ARGUMENTS` is empty → use default: !`cat ASSIGNMENT.md 2>/dev/null || echo "⚠ No assignment file found. Re-run as: /assignment path/to/ASSIGNMENT.md"`

Whichever loads successfully is the authoritative assignment for this run.

## Your Task

1. Start with a todo list and keep it current.
2. Preserve the deterministic boundary: LLM proposes; schemas, routes, guardrails, and tests decide.
3. Keep P0/P1/P2 scope explicit. Do not add P2 features unless the user asks.
4. Use the Builder, Reviewer, and Tester agent definitions under `.claude/agents/` when delegating.
5. Never invent requirements. If the assignment is ambiguous, document the assumption in README.
6. Before declaring completion, run the **Phase 5 JD Alignment bash script** from the protocol —
   every `grep` and `python3` assertion must exit 0.
7. Before declaring completion, run the **Phase 6 Assignment Requirements Gate** from the protocol —
   read the loaded assignment, extract every endpoint/MUST/evaluation requirement, verify each one,
   and paste the full checkbox report. Every box must be `[x]` before submit.
8. End with: files changed, pytest result, Phase 5 gate output, Phase 6 gate report.
9. **Phase 7 — Evaluator's Eye View**: after Phase 6 passes, run `/evaluate` on the submission:
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   cd "$REPO_ROOT/evaluator" && uv run evaluate --path "$(pwd)"
   ```
   Report total score, recommendation, and top 3 discussion questions.
   If any axis scores below 4, identify which phase should have caught the gap.

## Guardrails

- Do not post comments, open PRs, push, or alter remotes unless the user explicitly asks.
- Do not read `../.entire/metadata/**`.
- Do not log, print, or commit secrets.
- Do not bypass `AGENTS.md`; brand rules must be loaded just-in-time where the protocol requires it.
