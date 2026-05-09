import json
from datetime import UTC, datetime
from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db_models import (
    AuditEventRow,
    GuardrailCheckRow,
    IdempotencyRecord,
    PatchProposalRow,
    PlanStepRow,
    SessionRow,
)
from src.models import (
    GuardrailCheck,
    PatchProposal,
    PlanStep,
    Session,
)


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


class SQLiteRepository:
    """Concrete repository backed by async SQLite."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def save_session(self, session: Session) -> Session:
        row = SessionRow(
            id=session.id,
            title=session.title,
            description=session.description,
            brand=session.brand,
            trace_id=session.trace_id,
            owner_id=getattr(session, "owner_id", ""),
            created_at=session.created_at,
        )
        self._db.add(row)
        await self._db.commit()
        return session

    async def get_session(self, session_id: UUID) -> Optional[Session]:
        result = await self._db.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        # Load plan steps
        steps_result = await self._db.execute(
            select(PlanStepRow).where(PlanStepRow.session_id == session_id)
        )
        step_rows = steps_result.scalars().all()

        steps = []
        for step_row in step_rows:
            # Load patches for each step
            patches_result = await self._db.execute(
                select(PatchProposalRow).where(PatchProposalRow.step_id == step_row.id)
            )
            patch_rows = patches_result.scalars().all()

            patches = []
            for patch_row in patch_rows:
                checks_result = await self._db.execute(
                    select(GuardrailCheckRow).where(
                        GuardrailCheckRow.patch_id == patch_row.id
                    )
                )
                check_rows = checks_result.scalars().all()
                checks = [
                    GuardrailCheck(
                        ruleId=c.rule_id,
                        severity=c.severity,
                        result=c.result,
                        reason=c.reason,
                    )
                    for c in check_rows
                ]
                patches.append(
                    PatchProposal(
                        id=patch_row.id,
                        step_id=patch_row.step_id,
                        brand=patch_row.brand,
                        diff=patch_row.diff,
                        checks=checks,
                        created_at=patch_row.created_at,
                    )
                )

            steps.append(
                PlanStep(
                    id=step_row.id,
                    description=step_row.description,
                    target_files=step_row.get_target_files(),
                    patches=patches,
                )
            )

        return Session(
            id=row.id,
            title=row.title,
            description=row.description,
            brand=row.brand,
            trace_id=row.trace_id,
            owner_id=row.owner_id,
            steps=steps,
            created_at=row.created_at,
        )

    async def save_steps(
        self, session_id: UUID, steps: list[PlanStep]
    ) -> Optional[list[PlanStep]]:
        # Verify session exists
        result = await self._db.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        if result.scalar_one_or_none() is None:
            return None

        # Delete existing steps
        await self._db.execute(
            delete(PlanStepRow).where(PlanStepRow.session_id == session_id)
        )

        for step in steps:
            row = PlanStepRow(
                id=step.id,
                session_id=session_id,
                description=step.description,
                target_files=json.dumps(step.target_files),
            )
            self._db.add(row)

        await self._db.commit()
        return steps

    async def find_step(self, session_id: UUID, step_id: UUID) -> Optional[PlanStep]:
        result = await self._db.execute(
            select(PlanStepRow).where(
                PlanStepRow.session_id == session_id,
                PlanStepRow.id == step_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PlanStep(
            id=row.id,
            description=row.description,
            target_files=row.get_target_files(),
        )

    async def save_patch(
        self, session_id: UUID, patch: PatchProposal
    ) -> Optional[PatchProposal]:
        # Verify step belongs to session
        step = await self.find_step(session_id, patch.step_id)
        if step is None:
            return None

        row = PatchProposalRow(
            id=patch.id,
            step_id=patch.step_id,
            brand=patch.brand,
            diff=patch.diff,
            created_at=patch.created_at,
        )
        self._db.add(row)
        await self._db.commit()
        return patch

    async def get_patch(self, patch_id: UUID) -> Optional[PatchProposal]:
        result = await self._db.execute(
            select(PatchProposalRow).where(PatchProposalRow.id == patch_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        checks_result = await self._db.execute(
            select(GuardrailCheckRow).where(GuardrailCheckRow.patch_id == patch_id)
        )
        check_rows = checks_result.scalars().all()
        checks = [
            GuardrailCheck(
                ruleId=c.rule_id,
                severity=c.severity,
                result=c.result,
                reason=c.reason,
            )
            for c in check_rows
        ]

        return PatchProposal(
            id=row.id,
            step_id=row.step_id,
            brand=row.brand,
            diff=row.diff,
            checks=checks,
            created_at=row.created_at,
        )

    async def patch_belongs_to_session(self, session_id: UUID, patch_id: UUID) -> bool:
        result = await self._db.execute(
            select(PatchProposalRow).where(PatchProposalRow.id == patch_id)
        )
        patch_row = result.scalar_one_or_none()
        if patch_row is None:
            return False
        step = await self.find_step(session_id, patch_row.step_id)
        return step is not None

    async def get_patch_owner(self, patch_id: UUID) -> Optional[str]:
        result = await self._db.execute(
            select(SessionRow.owner_id)
            .join(PlanStepRow, PlanStepRow.session_id == SessionRow.id)
            .join(PatchProposalRow, PatchProposalRow.step_id == PlanStepRow.id)
            .where(PatchProposalRow.id == patch_id)
        )
        return result.scalar_one_or_none()

    async def save_checks(
        self, patch_id: UUID, checks: list[GuardrailCheck]
    ) -> Optional[list[GuardrailCheck]]:
        # Verify patch exists
        result = await self._db.execute(
            select(PatchProposalRow).where(PatchProposalRow.id == patch_id)
        )
        if result.scalar_one_or_none() is None:
            return None

        # Delete existing checks
        await self._db.execute(
            delete(GuardrailCheckRow).where(GuardrailCheckRow.patch_id == patch_id)
        )

        for check in checks:
            row = GuardrailCheckRow(
                patch_id=patch_id,
                rule_id=check.ruleId,
                severity=check.severity,
                result=check.result,
                reason=check.reason,
            )
            self._db.add(row)

        await self._db.commit()
        return checks

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
        row = AuditEventRow(
            trace_id=trace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            prompt=prompt,
            response=response,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        )
        self._db.add(row)
        await self._db.commit()

    async def get_idempotency(self, key: str) -> Optional[str]:
        result = await self._db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        # Check TTL (24h)
        age = datetime.now(UTC) - row.created_at.replace(tzinfo=UTC)
        if age.total_seconds() > 86400:
            return None
        return row.response_json

    async def set_idempotency(self, key: str, response_json: str) -> None:
        row = IdempotencyRecord(key=key, response_json=response_json)
        self._db.add(row)
        await self._db.commit()


class InMemoryRepository:
    """In-memory repository for tests — mirrors store.py logic, all methods async."""

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
