from src.models import Brand, ToolInvocation


class AuditStore:
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
                invocation for invocation in invocations if invocation.caller_brand == brand
            ]
        if limit is not None:
            return invocations[:limit]
        return invocations

    def clear(self) -> None:
        self._invocations.clear()


audit_store = AuditStore()
