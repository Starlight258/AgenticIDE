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

# 5. Init env
cp .env.example .env
# Edit .env with your real ANTHROPIC_API_KEY
source .venv/bin/activate  # Activate virtual environment

# 6. Smoke test
pytest                          # 1 passed
make dev       # http://localhost:8000 살아있는지 확인
```

Now timer starts. Spec disambiguation = first 30 min, no code.
