"""FastAPI entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db import create_tables  # noqa: E402
from src.exceptions import llm_unavailable_handler, not_found_handler, ownership_handler  # noqa: E402
from src.llm import LLMUnavailableError  # noqa: E402
from src.logging_config import configure_structlog  # noqa: E402
from src.routes import router  # noqa: E402
from src.errors import NotFoundError, OwnershipError  # noqa: E402

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog()

    settings = get_settings()
    await create_tables(settings.db_url)

    yield


app = FastAPI(title="case-01-session-second", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)

app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(OwnershipError, ownership_handler)
app.add_exception_handler(LLMUnavailableError, llm_unavailable_handler)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
