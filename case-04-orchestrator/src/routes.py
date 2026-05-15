"""HTTP routes for job orchestration."""

import asyncio
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from src.guardrails import run_checks
from src.models import AgentResult, GuardrailCheck, Job, Task
from src.schemas import DispatchOut, JobCreate, JobCreatedOut, JobOut, PROut, TaskOut
from src.store import jobs, lock

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=5)
TERMINAL_TASK_STATUSES = {"ready", "blocked", "failed"}


def _error(status_code: int, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=code)


def _get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found")
    return job


def _get_task(job: Job, task_id: str) -> Task:
    for task in job.tasks:
        if task.id == task_id:
            return task
    raise _error(status.HTTP_404_NOT_FOUND, "task_not_found")


def _task_out(task: Task) -> TaskOut:
    data = task.model_dump()
    if task.result is not None:
        data["diff"] = task.result.diff
    return TaskOut.model_validate(data)


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        status=job.status,
        brand=job.brand,
        trace_id=job.trace_id,
        created_at=job.created_at,
        tasks=[_task_out(task) for task in job.tasks],
    )


def _worktree_path(repo_path: str, job_id: str, task_index: int) -> Path:
    repo = Path(repo_path).expanduser().resolve()
    return repo.parent / f"wt-{job_id[:8]}-{task_index}"


def _branch_name(job_id: str, task_index: int) -> str:
    return f"agentic/{job_id[:8]}-{task_index}"


def _create_worktree(repo_path: str, worktree_path: Path, branch: str) -> None:
    subprocess.run(
        ["git", "-C", repo_path, "worktree", "add", "-b", branch, str(worktree_path)],
        check=True,
        capture_output=True,
        text=True,
    )


def _run_claude(task: Task) -> None:
    subprocess.run(
        ["claude", "-p", task.issue],
        cwd=task.worktree_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _collect_diff(task: Task) -> AgentResult:
    if task.worktree_path is None:
        return AgentResult(diff="", files=[])
    diff = subprocess.run(
        ["git", "diff"],
        cwd=task.worktree_path,
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    files = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=task.worktree_path,
        check=False,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    return AgentResult(diff=diff, files=files)


def _refresh_job_status(job: Job) -> None:
    statuses = {task.status for task in job.tasks}
    if not statuses <= TERMINAL_TASK_STATUSES:
        return
    job.status = "done" if statuses <= {"ready"} else "partial_failure"


def _finish_task(job_id: str, task_id: str) -> None:
    with lock:
        job = jobs[job_id]
        task = _get_task(job, task_id)
        task.status = "running"
    try:
        _run_claude(task)
        result = _collect_diff(task)
        checks = run_checks(result.diff, job.brand)
        task_status = "blocked" if _has_blocking_failure(checks) else "ready"
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        result = _collect_diff(task)
        checks = []
        task_status = "failed"
        result.diff = result.diff or str(exc)
    with lock:
        task.result = result
        task.diff = result.diff
        task.checks = checks
        task.status = task_status
        _refresh_job_status(job)


def _has_blocking_failure(checks: list[GuardrailCheck]) -> bool:
    return any(check.severity == "BLOCK" and check.result == "fail" for check in checks)


def _schedule_task(job_id: str, task_id: str) -> None:
    loop = asyncio.get_running_loop()
    loop.run_in_executor(executor, _finish_task, job_id, task_id)


def _create_pr(task: Task) -> str:
    if task.worktree_path is None:
        return f"https://github.com/local/orchestrator/pull/{task.branch}"
    result = subprocess.run(
        ["gh", "pr", "create", "--fill"],
        cwd=task.worktree_path,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().splitlines()[-1]
    return f"https://github.com/local/orchestrator/pull/{task.branch}"


def _remove_worktree(worktree_path: str | None) -> None:
    if worktree_path is None:
        return
    subprocess.run(
        ["git", "worktree", "remove", worktree_path],
        check=False,
        capture_output=True,
        text=True,
    )
    shutil.rmtree(worktree_path, ignore_errors=True)


@router.post("/jobs", response_model=JobCreatedOut, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate) -> JobCreatedOut:
    tasks = [Task(issue=issue) for issue in payload.issues]
    job = Job(
        title=payload.title,
        brand=payload.brand,
        repo_path=payload.repo_path,
        tasks=tasks,
    )
    with lock:
        jobs[job.id] = job
    return JobCreatedOut.model_validate(job.model_dump())


@router.post(
    "/jobs/{job_id}/dispatch",
    response_model=DispatchOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def dispatch_job(job_id: str) -> DispatchOut:
    with lock:
        job = _get_job(job_id)
        if job.status != "pending":
            raise _error(status.HTTP_409_CONFLICT, "already_dispatched")
        job.status = "dispatched"

    for index, task in enumerate(job.tasks):
        path = _worktree_path(job.repo_path, job.id, index)
        branch = _branch_name(job.id, index)
        _create_worktree(job.repo_path, path, branch)
        task.worktree_path = str(path)
        task.branch = branch
        _schedule_task(job.id, task.id)

    return DispatchOut(
        job_id=job.id,
        task_count=len(job.tasks),
        tasks=[_task_out(task) for task in job.tasks],
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str) -> JobOut:
    job = _get_job(job_id)
    return _job_out(job)


@router.get("/jobs/{job_id}/tasks/{tid}", response_model=TaskOut)
def get_task(job_id: str, tid: str) -> TaskOut:
    job = _get_job(job_id)
    return _task_out(_get_task(job, tid))


@router.post("/jobs/{job_id}/tasks/{tid}/pr", response_model=PROut)
def create_pr(job_id: str, tid: str) -> PROut:
    job = _get_job(job_id)
    task = _get_task(job, tid)
    if task.pr_url is not None:
        raise _error(status.HTTP_409_CONFLICT, "pr_already_exists")
    if task.status != "ready":
        raise _error(422, "task_not_ready")

    branch = task.branch or _branch_name(job.id, job.tasks.index(task))
    task.branch = branch
    task.pr_url = _create_pr(task)
    removed_path = task.worktree_path
    _remove_worktree(removed_path)
    task.worktree_path = None
    return PROut(pr_url=task.pr_url, branch=branch, worktree_path=removed_path)
