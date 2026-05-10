"""FastAPI entry point for the DH context injection server."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.audit_routes import router as audit_router
from src.routes import router as tools_router

app = FastAPI(title="DH Context Injection Server")
app.include_router(tools_router)
app.include_router(audit_router)


@app.exception_handler(RequestValidationError)
def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Keep caller identity errors aligned with the documented error model."""
    del request
    if missing_caller_brand(exc):
        return JSONResponse(
            status_code=400,
            content={"detail": "invalid X-Caller-Brand"},
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


def missing_caller_brand(exc: RequestValidationError) -> bool:
    """Return whether validation failed because X-Caller-Brand is absent."""
    return any(
        error.get("type") == "missing"
        and error.get("loc") == ("header", "X-Caller-Brand")
        for error in exc.errors()
    )
