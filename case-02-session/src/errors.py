"""Domain exception types shared across service, guards, and exception handlers."""

from uuid import UUID

from fastapi import HTTPException


class APIError(HTTPException):
    """Structured HTTP error. detail is a flat dict (no extra wrapping)."""

    def __init__(self, status_code: int, error: str, message: str, **extra) -> None:
        super().__init__(
            status_code=status_code,
            detail={"error": error, "message": message, **extra},
        )


class AlreadyCheckedError(Exception):
    """Raised when POST /check is called on a patch that already has results."""

    def __init__(self, patch_id: UUID, checks: list) -> None:
        self.patch_id = patch_id
        self.checks = checks


class NotFoundError(Exception):
    pass


class OwnershipError(Exception):
    pass
