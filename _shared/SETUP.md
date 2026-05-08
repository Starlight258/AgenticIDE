# New Case Study Setup (5 min)

Run from the `agenticIDE/` root.

```bash
# 1. Init project
uv init case-XX-NAME
cd case-XX-NAME

# 2. Add deps (adjust per case)
uv add anthropic pydantic pytest ruff python-dotenv "fastapi[standard]"

# 3. Copy boilerplate
cp ../_shared/README_5sections.md README.md
cp ../_shared/AGENTS.md AGENTS.md
cp ../_shared/.env.example .env.example
cp ../_shared/.gitignore.template .gitignore
cp ../_shared/Makefile.template Makefile

# 4. Project layout — src/ for code, tests/ for pytest
mkdir -p src tests
touch src/__init__.py
rm -f main.py                                    # remove uv init default

# FastAPI skeleton — replace [CASE_NAME] after pasting
cat > src/main.py <<'EOF'
"""FastAPI entry point. Replace [CASE_NAME] with the actual case identifier."""
from fastapi import FastAPI

app = FastAPI(title="[CASE_NAME]")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
EOF

# 5. Wire multi-agent workflow
mkdir -p .claude/agents
cp ../_shared/agents/*.md .claude/agents/
# builder.md / tester.md / reviewer.md — used by /iterate

# 6. Init env
cp .env.example .env
# Edit .env with your real ANTHROPIC_API_KEY
source .venv/bin/activate  # Activate virtual environment

# 7. Smoke test
pytest                          # 1 passed
make dev       # http://localhost:8000 살아있는지 확인
```

## Multi-agent workflow (available after step 5)

`~/.claude/commands/` 에 있는 글로벌 커맨드:

| Command | When to use |
|---|---|
| `/plan` | 시작 시 1회 — PROTOCOL.md 읽고 PLAN.md 생성, 승인 대기 |
| `/iterate <feature>` | PLAN.md 승인 후 — 기능 하나씩 Builder→Tester→Reviewer 루프 |

`.claude/agents/` 에 있는 프로젝트별 에이전트 정의:
- `builder.md` — 구현 규칙 (no print, absolute imports, ruff clean)
- `tester.md` — pytest + ruff 실행 후 PASS/FAIL 리포트
- `reviewer.md` — JD signal map + anti-pattern 체크

프로젝트별 커스텀이 필요하면 `.claude/agents/*.md` 를 직접 수정.

Now timer starts. Spec disambiguation = first 30 min, no code.
