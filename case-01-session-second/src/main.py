"""FastAPI entry point."""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402

from src.routes import router  # noqa: E402

app = FastAPI(title="case-01-session-second")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
