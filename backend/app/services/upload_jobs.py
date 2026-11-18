import logging
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.db.database import AsyncSessionLocal
from app.db.models import Document, UploadJob
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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


async def create_job(user_id: str | uuid.UUID, session: AsyncSession | None = None) -> str:
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
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> dict | None:
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
            if job.status in (UploadStatus.COMPLETED.value, UploadStatus.FAILED.value):
                _job_stages.pop(job_id, None)
        if "stage" in kwargs:
            if job.status not in (UploadStatus.COMPLETED.value, UploadStatus.FAILED.value):
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


async def get_job(job_id: str, session: AsyncSession | None = None) -> dict | None:
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


async def clear_jobs(session: AsyncSession | None = None) -> None:
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
    session: AsyncSession | None = None,
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


STALE_BUILDING_MINUTES = 15


def _as_utc(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_stale_building(doc, max_age_minutes: int = STALE_BUILDING_MINUTES) -> bool:
    """True if a document has been 'building' for longer than max_age_minutes."""
    if getattr(doc, "index_status", None) != "building":
        return False
    created = _as_utc(getattr(doc, "created_at", None))
    if created is None:
        return False
    return created < datetime.now(UTC) - timedelta(minutes=max_age_minutes)


async def fail_stale_building_documents(
    max_age_minutes: int = STALE_BUILDING_MINUTES,
    session: AsyncSession | None = None,
) -> int:
    """Mark documents stuck in 'building' longer than max_age_minutes as 'failed'. Returns rows updated."""
    cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)

    async def _run(s: AsyncSession) -> int:
        res = await s.execute(
            update(Document)
            .where(Document.index_status == "building", Document.created_at < cutoff)
            .values(index_status="failed")
        )
        await s.commit()
        return res.rowcount or 0

    if session is not None:
        return await _run(session)
    async with AsyncSessionLocal() as s:
        return await _run(s)


async def purge_expired_sample_documents(db: AsyncSession, user_id: uuid.UUID | None = None) -> int:
    """
    Finds all Document rows (for user_id if given, or globally) where is_sample_document(doc) is True
    AND doc.created_at < datetime.now(UTC) - timedelta(hours=24) (handling naive and timezone-aware created_at).
    Physically deletes their ChatDocument, ChatChunk, Chat, PatientFact (if any), UploadJob,
    local/GCS index files, and Document rows, and commits.
    Returns the count of purged sample documents.
    """
    import shutil

    from app.core.config import settings
    from app.db.models import (
        Chat,
        ChatChunk,
        ChatDocument,
        Document,
        PatientFact,
        UploadJob,
    )
    from app.rag.index_storage import adelete_index_artifacts
    from app.rag.retriever import evict_index_cache
    from app.services.clinical_units import is_sample_document
    from sqlalchemy import or_

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)

    stmt = select(Document)
    if user_id:
        stmt = stmt.filter(Document.user_id == user_id)
    res = await db.execute(stmt)
    all_docs = res.scalars().all()

    expired_sample_docs = []
    for d in all_docs:
        if not is_sample_document(d):
            continue
        c_at = d.created_at
        if c_at is None:
            continue
        if c_at.tzinfo is None:
            c_at = c_at.replace(tzinfo=UTC)
        if c_at < cutoff:
            expired_sample_docs.append(d)

    if not expired_sample_docs:
        return 0

    doc_ids = [d.id for d in expired_sample_docs]
    doc_id_strs = [str(d) for d in doc_ids]

    # Clean up index artifacts & vector cache
    for d in expired_sample_docs:
        if d.file_path:
            try:
                await adelete_index_artifacts(d.file_path)
            except Exception as e:
                logger.warning("Failed deleting index artifacts for expired sample doc %s: %s", d.id, e)
        try:
            evict_index_cache(str(d.id))
            if d.file_path:
                evict_index_cache(str(d.file_path))
        except Exception:
            pass
        try:
            session_cache = settings.VECTOR_CACHE_DIR / str(d.id)
            if session_cache.is_dir():
                shutil.rmtree(session_cache, ignore_errors=True)
        except Exception:
            pass

    # Find chats linked to these documents
    chats_res = await db.execute(select(Chat.id).filter(Chat.document_id.in_(doc_ids)))
    linked_chat_ids = set(chats_res.scalars().all())

    cd_res = await db.execute(select(ChatDocument.chat_id).filter(ChatDocument.document_id.in_(doc_ids)))
    for cid in cd_res.scalars().all():
        linked_chat_ids.add(cid)

    # Delete ChatDocuments
    cd_delete_conds = [ChatDocument.document_id.in_(doc_ids)]
    if linked_chat_ids:
        cd_delete_conds.append(ChatDocument.chat_id.in_(list(linked_chat_ids)))
    await db.execute(delete(ChatDocument).where(or_(*cd_delete_conds)))

    # Delete ChatChunks
    if linked_chat_ids:
        await db.execute(delete(ChatChunk).where(ChatChunk.chat_id.in_(list(linked_chat_ids))))

    # Delete Chats
    if linked_chat_ids:
        await db.execute(delete(Chat).where(Chat.id.in_(list(linked_chat_ids))))

    # Delete UploadJobs
    await db.execute(delete(UploadJob).where(UploadJob.document_id.in_(doc_id_strs)))

    # Delete PatientFacts if any were linked
    fact_conds = [PatientFact.source_id.in_(doc_id_strs)]
    if linked_chat_ids:
        fact_conds.append(PatientFact.source_id.in_([str(cid) for cid in linked_chat_ids]))
    await db.execute(delete(PatientFact).where(or_(*fact_conds)))

    # Delete Documents
    await db.execute(delete(Document).where(Document.id.in_(doc_ids)))

    await db.commit()
    logger.info("Purged %d expired sample documents (>24h TTL)", len(expired_sample_docs))
    return len(expired_sample_docs)


