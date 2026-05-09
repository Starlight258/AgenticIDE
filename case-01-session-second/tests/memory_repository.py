"""In-memory SessionRepository for tests — no DB, all methods async."""

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from src.models import GuardrailCheck, PatchProposal, PlanStep, Session


class InMemoryRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}
        self._patches: dict[UUID, PatchProposal] = {}
        self._idempotency: dict[str, tuple[str, datetime]] = {}
        self._audit_log: list[dict] = []

    def clear(self) -> None:
        self._sessions.clear()
        self._patches.clear()
        self._idempotency.clear()
        self._audit_log.clear()

    async def save_session(self, session: Session) -> Session:
        self._sessions[session.id] = session
        return session

    async def get_session(self, session_id: UUID) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def save_steps(
        self, session_id: UUID, steps: list[PlanStep]
    ) -> Optional[list[PlanStep]]:
        session = await self.get_session(session_id)
        if session is None:
            return None
        session.steps = steps
        return session.steps

    async def find_step(self, session_id: UUID, step_id: UUID) -> Optional[PlanStep]:
        session = await self.get_session(session_id)
        if session is None:
            return None
        return next((s for s in session.steps if s.id == step_id), None)

    async def save_patch(
        self, session_id: UUID, patch: PatchProposal
    ) -> Optional[PatchProposal]:
        step = await self.find_step(session_id, patch.step_id)
        if step is None:
            return None
        step.patches.append(patch)
        self._patches[patch.id] = patch
        return patch

    async def get_patch(self, patch_id: UUID) -> Optional[PatchProposal]:
        return self._patches.get(patch_id)

    async def patch_belongs_to_session(self, session_id: UUID, patch_id: UUID) -> bool:
        patch = await self.get_patch(patch_id)
        if patch is None:
            return False
        return await self.find_step(session_id, patch.step_id) is not None

    async def get_patch_owner(self, patch_id: UUID) -> Optional[str]:
        for session in self._sessions.values():
            for step in session.steps:
                if any(patch.id == patch_id for patch in step.patches):
                    return session.owner_id
        return None

    async def save_checks(
        self, patch_id: UUID, checks: list[GuardrailCheck]
    ) -> Optional[list[GuardrailCheck]]:
        patch = await self.get_patch(patch_id)
        if patch is None:
            return None
        patch.checks = checks
        return patch.checks

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
    ) -> None:
        self._audit_log.append(
            {
                "trace_id": trace_id,
                "actor": actor,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "prompt": prompt,
                "response": response,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
            }
        )

    async def get_idempotency(self, key: str) -> Optional[str]:
        record = self._idempotency.get(key)
        if record is None:
            return None
        response_json, created_at = record
        age = datetime.now(UTC) - created_at
        if age.total_seconds() > 86400:
            return None
        return response_json

    async def set_idempotency(self, key: str, response_json: str) -> None:
        self._idempotency[key] = (response_json, datetime.now(UTC))

    def get_audit_log(self) -> list[dict]:
        return list(self._audit_log)
