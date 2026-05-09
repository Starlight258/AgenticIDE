"""SessionRepository protocol — the contract all implementations must satisfy."""

from typing import Optional, Protocol
from uuid import UUID

from src.models import GuardrailCheck, PatchProposal, PlanStep, Session


class SessionRepository(Protocol):
    async def save_session(self, session: Session) -> Session: ...

    async def get_session(self, session_id: UUID) -> Optional[Session]: ...

    async def save_steps(
        self, session_id: UUID, steps: list[PlanStep]
    ) -> Optional[list[PlanStep]]: ...

    async def find_step(
        self, session_id: UUID, step_id: UUID
    ) -> Optional[PlanStep]: ...

    async def save_patch(
        self, session_id: UUID, patch: PatchProposal
    ) -> Optional[PatchProposal]: ...

    async def get_patch(self, patch_id: UUID) -> Optional[PatchProposal]: ...

    async def patch_belongs_to_session(
        self, session_id: UUID, patch_id: UUID
    ) -> bool: ...

    async def get_patch_owner(self, patch_id: UUID) -> Optional[str]: ...

    async def save_checks(
        self, patch_id: UUID, checks: list[GuardrailCheck]
    ) -> Optional[list[GuardrailCheck]]: ...

    async def log_audit(
        self,
        trace_id: UUID,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: UUID,
        prompt: Optional[str] = None,
        response: Optional[str] = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None: ...

    async def get_idempotency(self, key: str) -> Optional[str]: ...

    async def set_idempotency(self, key: str, response_json: str) -> None: ...
