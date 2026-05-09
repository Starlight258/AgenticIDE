"""SQLite-backed implementation of SessionRepository."""

import json
from datetime import UTC, datetime
from typing import Optional
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
from src.models import GuardrailCheck, PatchProposal, PlanStep, Session


class SQLiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def save_session(self, session: Session) -> Session:
        row = SessionRow(
            id=session.id,
            title=session.title,
            description=session.description,
            brand=session.brand,
            trace_id=session.trace_id,
            owner_id=session.owner_id,
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

        steps_result = await self._db.execute(
            select(PlanStepRow).where(PlanStepRow.session_id == session_id)
        )
        step_rows = steps_result.scalars().all()

        steps = []
        for step_row in step_rows:
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
        result = await self._db.execute(
            select(SessionRow).where(SessionRow.id == session_id)
        )
        if result.scalar_one_or_none() is None:
            return None

        await self._db.execute(
            delete(PlanStepRow).where(PlanStepRow.session_id == session_id)
        )
        for step in steps:
            self._db.add(PlanStepRow(
                id=step.id,
                session_id=session_id,
                description=step.description,
                target_files=json.dumps(step.target_files),
            ))
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
        if await self.find_step(session_id, patch.step_id) is None:
            return None
        self._db.add(PatchProposalRow(
            id=patch.id,
            step_id=patch.step_id,
            brand=patch.brand,
            diff=patch.diff,
            created_at=patch.created_at,
        ))
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
        checks = [
            GuardrailCheck(
                ruleId=c.rule_id,
                severity=c.severity,
                result=c.result,
                reason=c.reason,
            )
            for c in checks_result.scalars().all()
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
        return await self.find_step(session_id, patch_row.step_id) is not None

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
        result = await self._db.execute(
            select(PatchProposalRow).where(PatchProposalRow.id == patch_id)
        )
        if result.scalar_one_or_none() is None:
            return None

        await self._db.execute(
            delete(GuardrailCheckRow).where(GuardrailCheckRow.patch_id == patch_id)
        )
        for check in checks:
            self._db.add(GuardrailCheckRow(
                patch_id=patch_id,
                rule_id=check.ruleId,
                severity=check.severity,
                result=check.result,
                reason=check.reason,
            ))
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
        self._db.add(AuditEventRow(
            trace_id=trace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            prompt=prompt,
            response=response,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
        ))
        await self._db.commit()

    async def get_idempotency(self, key: str) -> Optional[str]:
        result = await self._db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.key == key)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        age = datetime.now(UTC) - row.created_at.replace(tzinfo=UTC)
        if age.total_seconds() > 86400:
            return None
        return row.response_json

    async def set_idempotency(self, key: str, response_json: str) -> None:
        self._db.add(IdempotencyRecord(key=key, response_json=response_json))
        await self._db.commit()
