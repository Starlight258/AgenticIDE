"""E2E tests for the full session → plan → patch → check workflow.

Uses FastAPI TestClient (no real server needed) and mock LLM mode
(no ANTHROPIC_API_KEY required). The mock diff deliberately contains
print() and requests.get() to exercise R4 + R5 BLOCK guardrails.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ANTHROPIC_API_KEY", "")  # force mock mode

from src.main import app  # noqa: E402
from src.store import sessions  # noqa: E402


@pytest.fixture(autouse=True)
def clear_store():
    sessions.clear()
    yield
    sessions.clear()


client = TestClient(app)


def _full_workflow() -> tuple[str, str, str]:
    """Run create → plan → patch and return (session_id, step_id, patch_id)."""
    r = client.post(
        "/sessions",
        json={"title": "add discount", "description": "add pricing/discount.py", "brand": "efood"},
    )
    assert r.status_code == 200
    session_id = r.json()["id"]

    r = client.post(f"/sessions/{session_id}/plan")
    assert r.status_code == 200
    steps = r.json()
    assert len(steps) >= 1
    step_id = steps[0]["id"]

    r = client.post(f"/sessions/{session_id}/steps/{step_id}/patches")
    assert r.status_code == 200
    patch_id = r.json()["id"]

    return session_id, step_id, patch_id


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_session_returns_trace_id():
    r = client.post(
        "/sessions",
        json={"title": "t", "description": "d", "brand": "efood"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "trace_id" in body
    assert body["brand"] == "efood"


def test_plan_attaches_steps_to_session():
    r = client.post(
        "/sessions",
        json={"title": "t", "description": "d", "brand": "efood"},
    )
    session_id = r.json()["id"]

    r = client.post(f"/sessions/{session_id}/plan")
    assert r.status_code == 200
    steps = r.json()
    assert len(steps) >= 1
    assert steps[0]["description"]
    assert steps[0]["target_files"]
    assert "patches" not in steps[0], "POST /plan must not return patches (Response Shape = Workflow Signal)"


def test_patch_response_has_no_checks():
    """POST /patches must not return checks — that responsibility belongs to /check."""
    session_id, step_id, _ = _full_workflow()
    r = client.post(f"/sessions/{session_id}/steps/{step_id}/patches")
    assert r.status_code == 200
    assert "checks" not in r.json(), "POST /patches must not return checks (SRP)"


def test_r4_print_is_block_in_e2e():
    session_id, step_id, patch_id = _full_workflow()
    r = client.post(f"/sessions/{session_id}/steps/{step_id}/patches/{patch_id}/check")
    assert r.status_code == 200
    checks = {c["ruleId"]: c for c in r.json()}
    assert checks["R4"]["result"] == "fail"
    assert checks["R4"]["severity"] == "BLOCK"


def test_r5_requests_is_block_in_e2e():
    session_id, step_id, patch_id = _full_workflow()
    r = client.post(f"/sessions/{session_id}/steps/{step_id}/patches/{patch_id}/check")
    assert r.status_code == 200
    checks = {c["ruleId"]: c for c in r.json()}
    assert checks["R5"]["result"] == "fail"
    assert checks["R5"]["severity"] == "BLOCK"


def test_full_state_nested():
    """GET /sessions/{id} returns steps → patches → checks fully nested."""
    session_id, step_id, patch_id = _full_workflow()
    client.post(f"/sessions/{session_id}/steps/{step_id}/patches/{patch_id}/check")

    r = client.get(f"/sessions/{session_id}")
    assert r.status_code == 200
    body = r.json()

    assert "trace_id" in body
    assert len(body["steps"]) >= 1
    step = body["steps"][0]
    assert len(step["patches"]) >= 1
    patch = step["patches"][0]
    assert len(patch["checks"]) == 5  # R1–R5 all evaluated

    checks = {c["ruleId"]: c for c in patch["checks"]}
    assert checks["R4"]["severity"] == "BLOCK"
    assert checks["R5"]["severity"] == "BLOCK"


def test_404_on_unknown_session():
    r = client.get("/sessions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_glovo_brand_accepted():
    r = client.post(
        "/sessions",
        json={"title": "t", "description": "d", "brand": "glovo"},
    )
    assert r.status_code == 200
    assert r.json()["brand"] == "glovo"
