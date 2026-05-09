from unittest.mock import patch

import pytest

from src import store
from src.models import PatchProposalInput, PlanStepInput

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


@pytest.fixture(autouse=True)
def mock_llm():
    with patch("src.llm.create_plan", return_value=_MOCK_PLAN):
        with patch("src.llm.create_patch", return_value=_MOCK_PATCH):
            yield


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()
