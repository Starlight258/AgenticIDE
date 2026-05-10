"""In-memory audit store."""

from src.models import Brand, ToolInvocation


class AuditStore:
    """Store tool invocation audit records in memory."""

    def __init__(self) -> None:
        self._invocations: list[ToolInvocation] = []

    def add(self, invocation: ToolInvocation) -> ToolInvocation:
        self._invocations.append(invocation)
        return invocation

    def list(
        self,
        *,
        brand: Brand | None = None,
        limit: int | None = None,
    ) -> list[ToolInvocation]:
        invocations = sorted(
            self._invocations,
            key=lambda invocation: invocation.called_at,
            reverse=True,
        )
        if brand is not None:
            invocations = [
                invocation
                for invocation in invocations
                if invocation.caller_brand == brand
            ]
        if limit is not None:
            return invocations[:limit]
        return invocations

    def clear(self) -> None:
        self._invocations.clear()


audit_store = AuditStore()


def add_invocation(invocation: ToolInvocation) -> None:
    """Append one invocation to the audit log."""
    audit_store.add(invocation)


def list_audit() -> list[ToolInvocation]:
    """Return audit records newest first."""
    return audit_store.list()
