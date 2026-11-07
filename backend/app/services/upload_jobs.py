import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional, Any
from enum import Enum
import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.db.models import UploadJob

logger = logging.getLogger(__name__)


class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


_job_stages: dict[str, str] = {}


def _job_to_dict(job: UploadJob) -> dict:
    stage = _job_stages.get(str(job.id))
    if not stage:
        if job.status == UploadStatus.COMPLETED.value:
            stage = "ready"
        elif job.status == UploadStatus.PROCESSING.value:
            stage = "extracting"
        else:
            stage = "validating"

    return {
        "id": str(job.id),
        "job_id": str(job.id),
        "user_id": str(job.user_id),
        "status": job.status,
        "stage": stage,
        "document_id": str(job.document_id) if job.document_id else None,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


async def create_job(user_id: str | uuid.UUID, session: Optional[AsyncSession] = None) -> str:
    """Persist a new upload job in PostgreSQL/Neon and return the unique job_id."""
    job_id = str(uuid.uuid4())
    _job_stages[job_id] = "validating"
    user_uuid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id

    async def _insert(s: AsyncSession):
        job = UploadJob(
            id=job_id,
            user_id=user_uuid,
            status=UploadStatus.PENDING.value,
            document_id=None,
            error=None,
        )
        s.add(job)
        await s.commit()

    if session is not None:
        await _insert(session)
    else:
        async with AsyncSessionLocal() as s:
            await _insert(s)

    return job_id


async def update_job(
    job_id: str,
    session: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Optional[dict]:
    """Update fields on a persisted upload job in PostgreSQL."""
    async def _update(s: AsyncSession):
        stmt = select(UploadJob).filter(UploadJob.id == job_id)
        res = await s.execute(stmt)
        job = res.scalars().first()
        if not job:
            return None

        if "status" in kwargs:
            val = kwargs["status"]
            job.status = val.value if isinstance(val, UploadStatus) else str(val)
        if "stage" in kwargs:
            _job_stages[job_id] = str(kwargs["stage"])
        if "document_id" in kwargs:
            val = kwargs["document_id"]
            job.document_id = str(val) if val is not None else None
        if "error" in kwargs:
            val = kwargs["error"]
            job.error = str(val) if val is not None else None

        job.updated_at = datetime.now(UTC)
        await s.commit()
        await s.refresh(job)
        return _job_to_dict(job)

    if session is not None:
        return await _update(session)
    else:
        async with AsyncSessionLocal() as s:
            return await _update(s)


async def get_job(job_id: str, session: Optional[AsyncSession] = None) -> Optional[dict]:
    """Retrieve an upload job from PostgreSQL by job_id."""
    async def _get(s: AsyncSession):
        stmt = select(UploadJob).filter(UploadJob.id == job_id)
        res = await s.execute(stmt)
        job = res.scalars().first()
        if not job:
            return None
        return _job_to_dict(job)

    if session is not None:
        return await _get(session)
    else:
        async with AsyncSessionLocal() as s:
            return await _get(s)


async def clear_jobs(session: Optional[AsyncSession] = None) -> None:
    """Clear all upload jobs from database (useful for test resets)."""
    async def _clear(s: AsyncSession):
        await s.execute(delete(UploadJob))
        await s.commit()

    if session is not None:
        await _clear(session)
    else:
        async with AsyncSessionLocal() as s:
            await _clear(s)


async def cleanup_stale_jobs(
    max_age_hours: int = 24,
    session: Optional[AsyncSession] = None,
) -> int:
    """Delete upload jobs older than max_age_hours to prevent database bloat."""
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)

    async def _cleanup(s: AsyncSession):
        stmt = delete(UploadJob).filter(UploadJob.created_at < cutoff)
        res = await s.execute(stmt)
        await s.commit()
        return res.rowcount or 0

    if session is not None:
        return await _cleanup(session)
    else:
        async with AsyncSessionLocal() as s:
            return await _cleanup(s)
