"""FastAPI entry point for case-01-session-backend."""
import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402

from src.routes import router  # noqa: E402

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Session Backend — Agentic IDE Integration Layer")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
