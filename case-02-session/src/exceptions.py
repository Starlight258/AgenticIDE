"""App-level exception handlers — registered in main.py."""

from fastapi import Request
from fastapi.responses import JSONResponse

from src.errors import NotFoundError, OwnershipError
from src.llm import LLMUnavailableError


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def ownership_handler(request: Request, exc: OwnershipError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def llm_unavailable_handler(
    request: Request, exc: LLMUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
