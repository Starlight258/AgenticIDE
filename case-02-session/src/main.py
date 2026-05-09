"""FastAPI entry point. Replace [CASE_NAME] with the actual case identifier."""
from fastapi import FastAPI

app = FastAPI(title="[CASE_NAME]")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
