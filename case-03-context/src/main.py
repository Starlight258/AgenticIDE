"""FastAPI entry point for the DH context injection server."""

from fastapi import FastAPI

from src.routes import router

app = FastAPI(title="DH Context Injection Server")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
