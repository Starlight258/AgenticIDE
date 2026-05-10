"""FastAPI entry point for the DH context injection server."""

from fastapi import FastAPI

from src.audit_routes import router as audit_router
from src.routes import router as tools_router

app = FastAPI(title="DH Context Injection Server")
app.include_router(tools_router)
app.include_router(audit_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
