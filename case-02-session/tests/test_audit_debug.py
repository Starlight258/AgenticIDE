from fastapi.testclient import TestClient

from src.deps import get_llm, get_repo, get_settings
from src.main import app
from src.models import Brand
from src.schemas import PatchProposalInput, PlanStepInput
from tests.memory_repository import InMemoryRepository

AUTH = {"Authorization": "Bearer test-token"}
client = TestClient(app)

_debug_repo = InMemoryRepository()


class AuditDebugLLM:
    async def create_plan(
        self,
        title: str,
        description: str,
        brand: Brand,
    ) -> list[PlanStepInput]:
        return [PlanStepInput(description="test", target_files=["src/test.py"])]

    async def create_patch(
        self,
        step: PlanStepInput,
        brand: Brand,
    ) -> PatchProposalInput:
        return PatchProposalInput(diff="--- a/src/test.py\n+++ b/src/test.py\n")


def test_audit_log_debug() -> None:
    _debug_repo.clear()

    from src.config import Settings

    test_settings = Settings(anthropic_api_key="", env="test")
    app.dependency_overrides[get_repo] = lambda: _debug_repo
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_llm] = lambda: AuditDebugLLM()

    resp = client.post(
        "/sessions",
        json={"title": "T", "description": "D", "brand": "efood"},
        headers=AUTH,
    )
    sid = resp.json()["id"]
    resp2 = client.post(f"/sessions/{sid}/plan", headers=AUTH)

    assert resp2.status_code == 200
    assert len(_debug_repo.get_audit_log()) >= 1
