from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.models import AgentResult
from src import routes

client = TestClient(app)


def _job_payload(repo_path: Path) -> dict[str, object]:
    return {
        "title": "checkout fixes",
        "issues": ["fix login", "fix pricing"],
        "repo_path": str(repo_path),
        "brand": "efood",
    }


def test_create_job_contract(tmp_path: Path) -> None:
    response = client.post("/jobs", json=_job_payload(tmp_path))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "title", "status", "brand", "trace_id", "created_at"}
    assert body["status"] == "pending"


def test_dispatch_rejects_second_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes, "_create_worktree", lambda *_args: None)
    monkeypatch.setattr(routes, "_schedule_task", lambda *_args: None)
    job_id = client.post("/jobs", json=_job_payload(tmp_path)).json()["id"]

    first = client.post(f"/jobs/{job_id}/dispatch")
    second = client.post(f"/jobs/{job_id}/dispatch")

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json() == {"detail": "already_dispatched"}


def test_dispatch_updates_task_to_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def finish_now(job_id: str, task_id: str) -> None:
        job = routes._get_job(job_id)
        task = routes._get_task(job, task_id)
        task.result = AgentResult(diff="+from src.ok import value", files=["ok.py"])
        task.diff = task.result.diff
        task.checks = routes.run_checks(task.diff, job.brand)
        task.status = "ready"
        routes._refresh_job_status(job)

    monkeypatch.setattr(routes, "_create_worktree", lambda *_args: None)
    monkeypatch.setattr(routes, "_schedule_task", finish_now)
    job_id = client.post("/jobs", json=_job_payload(tmp_path)).json()["id"]

    response = client.post(f"/jobs/{job_id}/dispatch")
    state = client.get(f"/jobs/{job_id}").json()

    assert response.status_code == 202
    assert state["status"] == "done"
    assert {task["status"] for task in state["tasks"]} == {"ready"}


def test_create_pr_requires_ready_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes, "_create_worktree", lambda *_args: None)
    monkeypatch.setattr(routes, "_schedule_task", lambda *_args: None)
    job_id = client.post("/jobs", json=_job_payload(tmp_path)).json()["id"]
    task_id = client.post(f"/jobs/{job_id}/dispatch").json()["tasks"][0]["id"]

    response = client.post(f"/jobs/{job_id}/tasks/{task_id}/pr")

    assert response.status_code == 422
    assert response.json() == {"detail": "task_not_ready"}


def test_create_pr_returns_url_and_clears_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    removed: list[str | None] = []

    def finish_now(job_id: str, task_id: str) -> None:
        job = routes._get_job(job_id)
        task = routes._get_task(job, task_id)
        task.status = "ready"
        routes._refresh_job_status(job)

    monkeypatch.setattr(routes, "_create_worktree", lambda *_args: None)
    monkeypatch.setattr(routes, "_schedule_task", finish_now)
    monkeypatch.setattr(
        routes, "_create_pr", lambda _task: "https://github.com/acme/repo/pull/1"
    )
    monkeypatch.setattr(routes, "_remove_worktree", removed.append)
    job_id = client.post("/jobs", json=_job_payload(tmp_path)).json()["id"]
    task_id = client.post(f"/jobs/{job_id}/dispatch").json()["tasks"][0]["id"]

    response = client.post(f"/jobs/{job_id}/tasks/{task_id}/pr")
    task = client.get(f"/jobs/{job_id}/tasks/{task_id}").json()

    assert response.status_code == 200
    assert response.json()["pr_url"] == "https://github.com/acme/repo/pull/1"
    assert removed == [response.json()["worktree_path"]]
    assert task["worktree_path"] is None
