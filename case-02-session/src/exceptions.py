"""App-level exception handlers — registered in main.py."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from src.errors import AlreadyCheckedError, NotFoundError, OwnershipError
from src.llm import LLMUnavailableError


async def structured_http_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Returns dict detail as flat body (not wrapped in {"detail": ...})."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def already_checked_handler(
    request: Request, exc: AlreadyCheckedError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": "checks_already_exist",
            "patch_id": str(exc.patch_id),
            "checks": [c.model_dump() for c in exc.checks],
        },
    )


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def ownership_handler(request: Request, exc: OwnershipError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def llm_unavailable_handler(
    request: Request, exc: LLMUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
