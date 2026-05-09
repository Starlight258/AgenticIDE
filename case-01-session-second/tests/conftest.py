import pytest

from src.config import Settings
from src.deps import get_llm, get_repo, get_settings
from src.main import app
from src.models import Brand
from src.models import PatchProposalInput, PlanStepInput
from src.repository import InMemoryRepository

_MOCK_PLAN = [
    PlanStepInput(
        description="Implement deterministic guardrail evaluation",
        target_files=["src/guardrails.py", "tests/test_guardrails.py"],
    )
]

_MOCK_PATCH = PatchProposalInput(
    diff=(
        "--- a/pricing/discount.py\n"
        "+++ b/pricing/discount.py\n"
        "@@ -0,0 +1,5 @@\n"
        "+from .utils import calc\n"
        "+def apply_discount(order, pct):\n"
        '+    """Apply discount to order."""\n'
        '+    print(f"Discount applied: {pct}")\n'
        "+    requests.get(provider_url)\n"
    )
)

# Single shared repo instance — reset between tests
_repo = InMemoryRepository()


class FakeLLM:
    async def create_plan(
        self,
        title: str,
        description: str,
        brand: Brand,
        settings: Settings,
    ) -> list[PlanStepInput]:
        return _MOCK_PLAN

    async def create_patch(
        self,
        step: PlanStepInput,
        brand: Brand,
        settings: Settings,
    ) -> PatchProposalInput:
        return _MOCK_PATCH


@pytest.fixture(autouse=True)
def reset_repo():
    _repo.clear()
    yield
    _repo.clear()


@pytest.fixture(autouse=True)
def override_dependencies():
    """Override DI to use InMemoryRepository and test Settings."""
    test_settings = Settings(anthropic_api_key="", env="test")

    app.dependency_overrides[get_repo] = lambda: _repo
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_llm] = lambda: FakeLLM()
    yield
    app.dependency_overrides.clear()


def get_test_repo() -> InMemoryRepository:
    """Return the shared test repository for inspection in tests."""
    return _repo
