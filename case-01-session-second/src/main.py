"""FastAPI entry point."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from opentelemetry import trace  # noqa: E402
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db import create_tables  # noqa: E402
from src.llm import LLMUnavailableError  # noqa: E402
from src.logging_config import configure_structlog  # noqa: E402
from src.routes import router  # noqa: E402
from src.service import NotFoundError, OwnershipError  # noqa: E402

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_structlog()

    # Set up OpenTelemetry
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Create DB tables
    settings = get_settings()
    await create_tables(settings.db_url)

    yield


app = FastAPI(title="case-01-session-second", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FastAPIInstrumentor.instrument_app(app)

app.include_router(router)


@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(OwnershipError)
async def ownership_handler(request: Request, exc: OwnershipError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(
    request: Request, exc: LLMUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
