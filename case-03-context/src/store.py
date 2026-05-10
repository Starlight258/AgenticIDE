"""In-memory audit store."""

from src.models import AuditRecord, ToolInvocation

_AUDIT_LOG: list[ToolInvocation] = []


def add_invocation(invocation: ToolInvocation) -> None:
    """Append one invocation to the audit log."""
    _AUDIT_LOG.append(invocation)


def list_audit() -> list[AuditRecord]:
    """Return audit records in insertion order."""
    return [AuditRecord.model_validate(item.model_dump()) for item in _AUDIT_LOG]
