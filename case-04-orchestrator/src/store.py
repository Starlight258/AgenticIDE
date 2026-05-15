"""In-memory storage for jobs."""

from threading import Lock

from src.models import Job

jobs: dict[str, Job] = {}
lock = Lock()
