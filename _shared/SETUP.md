# New Case Study Setup (5 min)

Run from the `agenticIDE/` root.

```bash
# 1. Init project
uv init case-XX-NAME
cd case-XX-NAME

# 2. Add deps (adjust per case)
uv add anthropic pydantic pytest ruff python-dotenv fastapi uvicorn

# 3. Copy boilerplate
cp ../_shared/README_5sections.md README.md
cp ../_shared/AGENTS.md AGENTS.md
cp ../_shared/.env.example .env.example
cp ../_shared/.gitignore.template .gitignore
cp ../_shared/Makefile.template Makefile

# 4. Init env
cp .env.example .env
# Edit .env with your real ANTHROPIC_API_KEY
source .venv/bin/activate  # Activate virtual environment

# 5. Smoke test
pytest  # passes with the hello-world test
```

Now timer starts. Spec disambiguation = first 30 min, no code.
