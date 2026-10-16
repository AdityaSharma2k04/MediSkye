import uuid
from datetime import datetime, UTC
from typing import Optional
from enum import Enum


class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# In-memory job store (single-worker Render deployment — fine for beta)
_jobs: dict[str, dict] = {}


def create_job(user_id: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "user_id": user_id,
        "status": UploadStatus.PENDING,
        "document_id": None,
        "error": None,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return job_id


def update_job(job_id: str, **kwargs):
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


def clear_jobs():
    """Clear all in-memory jobs (useful for test resets)."""
    _jobs.clear()
