from uuid import uuid4

from fastapi.testclient import TestClient

from src.deps import get_llm
from src.llm import LLMUnavailableError
from src.main import app
from src.models import Brand, PatchProposalInput, PlanStepInput
from src.config import Settings

client = TestClient(app)

# Default auth header for all tests
AUTH = {"Authorization": "Bearer test-token"}
OTHER_AUTH = {"Authorization": "Bearer other-token"}


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_full_session_workflow_uses_spec_endpoint() -> None:
    session = _create_session()
    session_id = session["id"]

    plan_response = client.post(f"/sessions/{session_id}/plan", headers=AUTH)
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert len(plan) >= 1
    assert "patches" not in plan[0]

    patch_response = client.post(
        f"/sessions/{session_id}/patches",
        json={"step_id": plan[0]["id"]},
        headers=AUTH,
    )
    assert patch_response.status_code == 200
    patch = patch_response.json()
    assert patch["step_id"] == plan[0]["id"]
    assert "checks" not in patch

    # spec endpoint: POST /sessions/{id}/patches/{patchId}/check
    check_response = client.post(
        f"/sessions/{session_id}/patches/{patch['id']}/check", headers=AUTH
    )
    assert check_response.status_code == 200
    checks = check_response.json()
    assert len(checks) == 5
    assert {check["ruleId"] for check in checks} == {"R1", "R2", "R3", "R4", "R5"}

    get_response = client.get(f"/sessions/{session_id}", headers=AUTH)
    assert get_response.status_code == 200
    nested = get_response.json()
    assert nested["steps"][0]["patches"][0]["checks"] == checks


def test_spec_endpoint_blocks_r4_and_r5_from_sample_diff() -> None:
    """Sample diff (print + requests.get) must produce R4=BLOCK and R5=BLOCK."""
    session = _create_session()
    session_id = session["id"]

    plan = client.post(f"/sessions/{session_id}/plan", headers=AUTH).json()
    patch = client.post(
        f"/sessions/{session_id}/patches",
        json={"step_id": plan[0]["id"]},
        headers=AUTH,
    ).json()

    checks = client.post(
        f"/sessions/{session_id}/patches/{patch['id']}/check", headers=AUTH
    ).json()
    by_rule = {c["ruleId"]: c for c in checks}

    assert by_rule["R4"]["result"] == "fail"
    assert by_rule["R4"]["severity"] == "BLOCK"
    assert by_rule["R5"]["result"] == "fail"
    assert by_rule["R5"]["severity"] == "BLOCK"
    # apply_discount has a docstring → R3 passes
    assert by_rule["R3"]["result"] == "pass"
    # no os.system/subprocess → R2 passes
    assert by_rule["R2"]["result"] == "pass"


def test_spec_endpoint_rejects_patch_from_different_session() -> None:
    session_a = _create_session()
    session_b = _create_session()

    plan_a = client.post(f"/sessions/{session_a['id']}/plan", headers=AUTH).json()
    patch_a = client.post(
        f"/sessions/{session_a['id']}/patches",
        json={"step_id": plan_a[0]["id"]},
        headers=AUTH,
    ).json()

    response = client.post(
        f"/sessions/{session_b['id']}/patches/{patch_a['id']}/check", headers=AUTH
    )
    assert response.status_code == 404


def test_create_session_returns_empty_steps_and_server_fields() -> None:
    session = _create_session()

    assert session["brand"] == "efood"
    assert session["steps"] == []
    assert "trace_id" in session
    assert "created_at" in session


def test_brand_outside_literal_returns_422() -> None:
    response = client.post(
        "/sessions",
        json={"title": "Title", "description": "Description", "brand": "unknown"},
        headers=AUTH,
    )

    assert response.status_code == 422


def test_missing_session_returns_404() -> None:
    response = client.get(f"/sessions/{uuid4()}", headers=AUTH)

    assert response.status_code == 404


def test_missing_step_returns_404() -> None:
    session = _create_session()
    response = client.post(
        f"/sessions/{session['id']}/patches",
        json={"step_id": str(uuid4())},
        headers=AUTH,
    )

    assert response.status_code == 404


def test_missing_patch_returns_404() -> None:
    response = client.post(f"/patches/{uuid4()}/check", headers=AUTH)

    assert response.status_code == 404


def test_missing_patch_via_spec_endpoint_returns_404() -> None:
    session = _create_session()
    response = client.post(
        f"/sessions/{session['id']}/patches/{uuid4()}/check", headers=AUTH
    )

    assert response.status_code == 404


def test_check_is_idempotent_and_overwrites_checks() -> None:
    session = _create_session()
    plan = client.post(f"/sessions/{session['id']}/plan", headers=AUTH).json()
    patch = client.post(
        f"/sessions/{session['id']}/patches",
        json={"step_id": plan[0]["id"]},
        headers=AUTH,
    ).json()
    session_id = session["id"]

    first = client.post(
        f"/sessions/{session_id}/patches/{patch['id']}/check", headers=AUTH
    ).json()
    second = client.post(
        f"/sessions/{session_id}/patches/{patch['id']}/check", headers=AUTH
    ).json()
    nested = client.get(f"/sessions/{session_id}", headers=AUTH).json()

    assert second == first
    assert nested["steps"][0]["patches"][0]["checks"] == second


# --- New tests ---


def test_auth_rejects_missing_token() -> None:
    """POST /sessions without Authorization header → 403."""
    response = client.post(
        "/sessions",
        json={
            "title": "AI coding session",
            "description": "Test",
            "brand": "efood",
        },
    )
    assert response.status_code == 403


def test_session_owner_is_required_for_session_workflow() -> None:
    session = _create_session()

    get_response = client.get(f"/sessions/{session['id']}", headers=OTHER_AUTH)
    assert get_response.status_code == 403

    plan_response = client.post(f"/sessions/{session['id']}/plan", headers=OTHER_AUTH)
    assert plan_response.status_code == 403

    plan = client.post(f"/sessions/{session['id']}/plan", headers=AUTH).json()
    patch = client.post(
        f"/sessions/{session['id']}/patches",
        json={"step_id": plan[0]["id"]},
        headers=AUTH,
    ).json()

    spec_check_response = client.post(
        f"/sessions/{session['id']}/patches/{patch['id']}/check",
        headers=OTHER_AUTH,
    )
    assert spec_check_response.status_code == 403

    shortcut_check_response = client.post(
        f"/patches/{patch['id']}/check",
        headers=OTHER_AUTH,
    )
    assert shortcut_check_response.status_code == 403


def test_idempotency_returns_cached_plan() -> None:
    """Second call with same Idempotency-Key returns cached response, no LLM call."""
    session = _create_session()
    session_id = session["id"]
    idem_key = "test-idem-key-unique-1234"
    headers = {**AUTH, "Idempotency-Key": idem_key}

    first = client.post(f"/sessions/{session_id}/plan", headers=headers)
    assert first.status_code == 200
    first_plan = first.json()

    second = client.post(f"/sessions/{session_id}/plan", headers=headers)
    assert second.status_code == 200
    second_plan = second.json()

    assert first_plan == second_plan


def test_circuit_breaker_returns_503_after_llm_failures() -> None:
    """When LLM raises LLMUnavailableError the endpoint returns 503."""

    class FailingLLM:
        async def create_plan(
            self,
            title: str,
            description: str,
            brand: Brand,
            settings: Settings,
        ) -> list[PlanStepInput]:
            raise LLMUnavailableError("LLM unavailable")

        async def create_patch(
            self,
            step: PlanStepInput,
            brand: Brand,
            settings: Settings,
        ) -> PatchProposalInput:
            raise LLMUnavailableError("LLM unavailable")

    app.dependency_overrides[get_llm] = lambda: FailingLLM()
    session = _create_session()
    response = client.post(
        f"/sessions/{session['id']}/plan",
        headers=AUTH,
    )
    assert response.status_code == 503


def test_audit_log_records_llm_call() -> None:
    """Service logs an audit entry in the repo after every plan creation."""
    from conftest import get_test_repo

    repo = get_test_repo()
    session = _create_session()
    response = client.post(f"/sessions/{session['id']}/plan", headers=AUTH)
    assert response.status_code == 200

    log = repo.get_audit_log()
    assert len(log) >= 1
    entry = log[0]
    assert entry["action"] == "create_plan"
    assert entry["resource_type"] == "session"
    assert entry["actor"] == "test-token"


def _create_session() -> dict[str, object]:
    response = client.post(
        "/sessions",
        json={
            "title": "AI coding session",
            "description": "Implement deterministic efood guardrails",
            "brand": "efood",
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    return response.json()
