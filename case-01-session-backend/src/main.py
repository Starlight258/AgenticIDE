"""FastAPI entry point for case-01-session-backend."""
import logging

from fastapi import FastAPI

from src.routes import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Session Backend — Agentic IDE Integration Layer")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
