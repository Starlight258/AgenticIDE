"""HTTP routes for audit inspection."""

from fastapi import APIRouter, Query

from src.models import Brand, ToolInvocation
from src.store import audit_store

router = APIRouter()


@router.get("/audit")
def get_audit(
    brand: Brand | None = None,
    limit: int | None = Query(default=None, ge=1),
) -> list[ToolInvocation]:
    return audit_store.list(brand=brand, limit=limit)
