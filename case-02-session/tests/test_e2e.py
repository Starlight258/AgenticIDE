from uuid import uuid4

from fastapi.testclient import TestClient

from src.deps import get_llm
from src.llm import LLMUnavailableError
from src.main import app
from src.models import Brand
from src.routes import router
from src.schemas import PatchProposalInput, PlanStepInput

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
        f"/sessions/{session_id}/plan/{plan[0]['id']}/patches",
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


def test_second_check_returns_409_with_existing_checks() -> None:
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
    )
    nested = client.get(f"/sessions/{session_id}", headers=AUTH).json()

    assert second.status_code == 409
    assert second.json()["error"] == "checks_already_exist"
    assert second.json()["checks"] == first
    assert nested["steps"][0]["patches"][0]["checks"] == first


def test_readiness_uses_latest_patch_even_if_unchecked() -> None:
    class CleanThenUncheckedLLM:
        calls = 0

        async def create_plan(
            self,
            title: str,
            description: str,
            brand: Brand,
        ) -> list[PlanStepInput]:
            return [
                PlanStepInput(description="Update handler", target_files=["app.py"])
            ]

        async def create_patch(
            self,
            step: PlanStepInput,
            brand: Brand,
        ) -> PatchProposalInput:
            self.calls += 1
            if self.calls == 1:
                return PatchProposalInput(
                    diff=(
                        "--- a/app.py\n"
                        "+++ b/app.py\n"
                        "@@ -0,0 +1,3 @@\n"
                        "+def handler():\n"
                        '+    """Handle request."""\n'
                        "+    return None\n"
                    )
                )
            return PatchProposalInput(
                diff="--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,1 @@\n+value = 1\n"
            )

    llm = CleanThenUncheckedLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    session = _create_session()
    plan = client.post(f"/sessions/{session['id']}/plan", headers=AUTH).json()
    step_id = plan[0]["id"]

    first_patch = client.post(
        f"/sessions/{session['id']}/plan/{step_id}/patches", headers=AUTH
    ).json()
    first_check = client.post(
        f"/sessions/{session['id']}/patches/{first_patch['id']}/check", headers=AUTH
    )
    assert first_check.status_code == 200

    ready = client.get(
        f"/sessions/{session['id']}/plan/{step_id}/readiness", headers=AUTH
    ).json()
    assert ready["verdict"] == "READY"
    assert ready["latest_patch_id"] == first_patch["id"]

    second_patch = client.post(
        f"/sessions/{session['id']}/plan/{step_id}/patches", headers=AUTH
    ).json()
    latest = client.get(
        f"/sessions/{session['id']}/plan/{step_id}/readiness", headers=AUTH
    ).json()

    assert latest["verdict"] == "NOT_READY"
    assert latest["latest_patch_id"] == second_patch["id"]
    assert latest["block_count"] == 0
    assert latest["warn_count"] == 0


def test_test_run_records_patch_ids_on_session() -> None:
    session = _create_session()
    plan = client.post(f"/sessions/{session['id']}/plan", headers=AUTH).json()
    patch = client.post(
        f"/sessions/{session['id']}/plan/{plan[0]['id']}/patches", headers=AUTH
    ).json()

    response = client.post(
        f"/sessions/{session['id']}/test-runs",
        json={"patch_ids": [patch["id"]], "outcome": "PARTIAL", "notes": "local only"},
        headers=AUTH,
    )

    assert response.status_code == 200
    test_run = response.json()
    assert test_run["session_id"] == session["id"]
    assert test_run["patch_ids"] == [patch["id"]]
    assert test_run["outcome"] == "PARTIAL"

    nested = client.get(f"/sessions/{session['id']}", headers=AUTH).json()
    assert nested["test_runs"][0]["id"] == test_run["id"]


def test_test_run_rejects_patch_from_other_session() -> None:
    session_a = _create_session()
    session_b = _create_session()
    plan_a = client.post(f"/sessions/{session_a['id']}/plan", headers=AUTH).json()
    patch_a = client.post(
        f"/sessions/{session_a['id']}/plan/{plan_a[0]['id']}/patches", headers=AUTH
    ).json()

    response = client.post(
        f"/sessions/{session_b['id']}/test-runs",
        json={"patch_ids": [patch_a["id"]], "outcome": "FAIL"},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.json()["error"] == "patch_not_in_session"


def test_glovo_mock_sample_diff_flags_all_guardrails() -> None:
    session = _create_session(brand="glovo")
    plan = client.post(f"/sessions/{session['id']}/plan", headers=AUTH).json()
    patch = client.post(
        f"/sessions/{session['id']}/plan/{plan[0]['id']}/patches", headers=AUTH
    ).json()

    response = client.post(
        f"/sessions/{session['id']}/patches/{patch['id']}/check", headers=AUTH
    )

    assert response.status_code == 200
    checks = response.json()
    assert {check["ruleId"] for check in checks} == {"G1", "G2", "G3", "G4", "G5"}
    assert all(check["result"] == "fail" for check in checks)


def test_router_has_at_least_8_routes() -> None:
    assert len(router.routes) >= 8


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
        ) -> list[PlanStepInput]:
            raise LLMUnavailableError("LLM unavailable")

        async def create_patch(
            self,
            step: PlanStepInput,
            brand: Brand,
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


def _create_session(brand: Brand = "efood") -> dict[str, object]:
    response = client.post(
        "/sessions",
        json={
            "title": "AI coding session",
            "description": "Implement deterministic efood guardrails",
            "brand": brand,
        },
        headers=AUTH,
    )

    assert response.status_code == 200
    return response.json()
