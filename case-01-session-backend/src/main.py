"""FastAPI entry point for case-01-session-backend."""
from fastapi import FastAPI

app = FastAPI(title="Case 01 — Session Backend")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
