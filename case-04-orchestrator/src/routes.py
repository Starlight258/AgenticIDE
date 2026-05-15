"""HTTP routes for job orchestration."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from src.models import Job, Task
from src.schemas import DispatchOut, JobCreate, JobCreatedOut, JobOut, PROut, TaskOut
from src.store import jobs, lock

router = APIRouter()


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
def dispatch_job(job_id: str) -> DispatchOut:
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
        raise _error(status.HTTP_422_UNPROCESSABLE_ENTITY, "task_not_ready")

    branch = task.branch or _branch_name(job.id, job.tasks.index(task))
    task.pr_url = f"https://github.com/local/orchestrator/pull/{branch}"
    removed_path = task.worktree_path
    task.worktree_path = None
    return PROut(pr_url=task.pr_url, branch=branch, worktree_path=removed_path)
