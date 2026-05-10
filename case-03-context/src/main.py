"""FastAPI entry point. Replace [CASE_NAME] with the actual case identifier."""
from fastapi import FastAPI

from src.audit_routes import router as audit_router

app = FastAPI(title="[CASE_NAME]")
app.include_router(audit_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
