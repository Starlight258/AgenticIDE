from uuid import uuid4

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_full_session_workflow_uses_spec_endpoint() -> None:
    session = _create_session()
    session_id = session["id"]

    plan_response = client.post(f"/sessions/{session_id}/plan")
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert len(plan) >= 1
    assert "patches" not in plan[0]

    patch_response = client.post(
        f"/sessions/{session_id}/patches",
        json={"step_id": plan[0]["id"]},
    )
    assert patch_response.status_code == 200
    patch = patch_response.json()
    assert patch["step_id"] == plan[0]["id"]
    assert "checks" not in patch

    # spec endpoint: POST /sessions/{id}/patches/{patchId}/check
    check_response = client.post(f"/sessions/{session_id}/patches/{patch['id']}/check")
    assert check_response.status_code == 200
    checks = check_response.json()
    assert len(checks) == 5
    assert {check["ruleId"] for check in checks} == {"R1", "R2", "R3", "R4", "R5"}

    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    nested = get_response.json()
    assert nested["steps"][0]["patches"][0]["checks"] == checks


def test_spec_endpoint_blocks_r4_and_r5_from_sample_diff() -> None:
    """Sample diff (print + requests.get) must produce R4=BLOCK and R5=BLOCK."""
    session = _create_session()
    session_id = session["id"]

    plan = client.post(f"/sessions/{session_id}/plan").json()
    patch = client.post(
        f"/sessions/{session_id}/patches",
        json={"step_id": plan[0]["id"]},
    ).json()

    checks = client.post(f"/sessions/{session_id}/patches/{patch['id']}/check").json()
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

    plan_a = client.post(f"/sessions/{session_a['id']}/plan").json()
    patch_a = client.post(
        f"/sessions/{session_a['id']}/patches",
        json={"step_id": plan_a[0]["id"]},
    ).json()

    response = client.post(f"/sessions/{session_b['id']}/patches/{patch_a['id']}/check")
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
    )

    assert response.status_code == 422


def test_missing_session_returns_404() -> None:
    response = client.get(f"/sessions/{uuid4()}")

    assert response.status_code == 404


def test_missing_step_returns_404() -> None:
    session = _create_session()
    response = client.post(
        f"/sessions/{session['id']}/patches",
        json={"step_id": str(uuid4())},
    )

    assert response.status_code == 404


def test_missing_patch_returns_404() -> None:
    response = client.post(f"/patches/{uuid4()}/check")

    assert response.status_code == 404


def test_missing_patch_via_spec_endpoint_returns_404() -> None:
    session = _create_session()
    response = client.post(f"/sessions/{session['id']}/patches/{uuid4()}/check")

    assert response.status_code == 404


def test_check_is_idempotent_and_overwrites_checks() -> None:
    session = _create_session()
    plan = client.post(f"/sessions/{session['id']}/plan").json()
    patch = client.post(
        f"/sessions/{session['id']}/patches",
        json={"step_id": plan[0]["id"]},
    ).json()
    session_id = session["id"]

    first = client.post(f"/sessions/{session_id}/patches/{patch['id']}/check").json()
    second = client.post(f"/sessions/{session_id}/patches/{patch['id']}/check").json()
    nested = client.get(f"/sessions/{session_id}").json()

    assert second == first
    assert nested["steps"][0]["patches"][0]["checks"] == second


def _create_session() -> dict[str, object]:
    response = client.post(
        "/sessions",
        json={
            "title": "AI coding session",
            "description": "Implement deterministic efood guardrails",
            "brand": "efood",
        },
    )

    assert response.status_code == 200
    return response.json()
