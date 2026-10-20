import os
import tempfile
import time
import uuid
import asyncio
import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import User, Document, DependentProfile
from app.schemas.upload import UploadResponse, UploadJobResponse, UploadStatusResponse
from app.services.pdf_service import validate_file_upload
from app.rag.loader import PDFExtractionError, extract_text_from_file
from app.core.audit import log_audit
from app.rag.retriever import create_hybrid_index, acreate_hybrid_index
from app.services.upload_jobs import create_job, update_job, get_job, UploadStatus
from app.rag.index_storage import asave_index_artifacts
from app.api.v1.endpoints.metrics import extract_and_cache_metrics

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_upload_background(
    job_id: str,
    tmp_path: str,
    filename: str,
    user_id: str,
    dependent_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    client_host: str = "unknown",
):
    """
    Background worker for PDF extraction, embedding, FAISS indexing, and DB commitment.
    Creates its own AsyncSessionLocal to ensure DB operations outlive the HTTP request.
    """
    from app.db.database import AsyncSessionLocal
    from app.db.models import Document, ChatDocument, Chat

    t_start = time.monotonic()
    logger.info(f"[UPLOAD {job_id}] START")

    await update_job(job_id, status=UploadStatus.PROCESSING)

    async with AsyncSessionLocal() as db:
        try:
            # Initial DB setup (document record & chat link)
            t0 = time.monotonic()
            user_uuid = uuid.UUID(user_id)
            dep_uuid = uuid.UUID(dependent_id) if dependent_id else None

            # Create Document record in DB
            doc = Document(
                user_id=user_uuid,
                dependent_id=dep_uuid,
                filename=filename,
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)

            # If active chat_id provided, link document to active chat session via ChatDocument
            if chat_id:
                try:
                    c_uuid = uuid.UUID(chat_id)
                    chat_res = await db.execute(
                        select(Chat).filter(Chat.id == c_uuid, Chat.user_id == user_uuid)
                    )
                    chat_obj = chat_res.scalars().first()
                    if chat_obj:
                        cd = ChatDocument(chat_id=chat_obj.id, document_id=doc.id)
                        db.add(cd)
                        await db.commit()
                except Exception as ce:
                    logger.warning(f"Failed to link chat {chat_id} to document {doc.id}: {ce}")
            logger.info(f"[UPLOAD {job_id}] Initial DB setup: {time.monotonic() - t0:.2f}s")

            # 1. Text extraction
            t0 = time.monotonic()
            page_docs = await extract_text_from_file(tmp_path, filename)
            logger.info(f"[UPLOAD {job_id}] Extraction: {time.monotonic() - t0:.2f}s ({len(page_docs)} pages)")

            # Audit logging
            t0 = time.monotonic()
            has_xray = any(d.metadata.get("type") == "xray" for d in page_docs)
            if has_xray:
                await log_audit(db, "XRAY_ANALYSIS", user_uuid, "upload", client_host, dependent_id=dep_uuid)

            await log_audit(db, "PDF_UPLOADED", user_uuid, f"doc_{doc.id}", client_host, dependent_id=dep_uuid)
            logger.info(f"[UPLOAD {job_id}] Audit logging: {time.monotonic() - t0:.2f}s")

            # 2. Create hybrid index (FAISS + BM25) and save to disk
            t0 = time.monotonic()
            index_dir = settings.INDEX_STORAGE_DIR
            index_dir.mkdir(parents=True, exist_ok=True)
            index_path = str(index_dir / f"user_{user_uuid}_doc_{doc.id}.index")

            _, _, chunks = await acreate_hybrid_index(page_docs, index_path)
            logger.info(f"[UPLOAD {job_id}] Index build: {time.monotonic() - t0:.2f}s ({len(chunks)} chunks)")

            # Sync index artifacts to GCS if configured
            await asave_index_artifacts(index_path)

            # 3. Update DB with file_path and commit
            t0 = time.monotonic()
            doc.file_path = index_path
            await db.commit()
            logger.info(f"[UPLOAD {job_id}] DB commit: {time.monotonic() - t0:.2f}s")

            # 4. Pre-generate and cache lab metrics (non-fatal)
            t0 = time.monotonic()
            try:
                metrics_result = await extract_and_cache_metrics(
                    doc_id=doc.id,
                    page_docs=page_docs,
                    db=db,
                    user_id=user_uuid,
                )
                if metrics_result is not None:
                    doc.cached_metrics = metrics_result
                    db.add(doc)
                    await db.commit()
                logger.info(
                    f"[UPLOAD {job_id}] Pre-generated {len(metrics_result) if metrics_result else 0} lab metrics in {time.monotonic() - t0:.2f}s"
                )
            except Exception as me:
                logger.error(f"[UPLOAD {job_id}] Lab metrics pre-generation error (non-fatal): {me}", exc_info=True)

            await update_job(job_id, status=UploadStatus.COMPLETED, document_id=str(doc.id))
            logger.info(f"[UPLOAD {job_id}] TOTAL: {time.monotonic() - t_start:.2f}s")
        except Exception as e:
            logger.error(f"[UPLOAD {job_id}] Failed after {time.monotonic() - t_start:.2f}s: {e}", exc_info=True)
            await update_job(job_id, status=UploadStatus.FAILED, error=str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=UploadJobResponse, tags=["PDF Upload"])
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    chat_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    validate_file_upload(content, filename=file.filename or "report.pdf")

    dep_id = None
    if patient_id and patient_id.lower() != "self" and patient_id != str(current_user.id):
        try:
            parsed_uuid = uuid.UUID(patient_id)
            res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == parsed_uuid,
                    DependentProfile.user_id == current_user.id
                )
            )
            dep = res.scalars().first()
            if not dep:
                raise HTTPException(status_code=404, detail="Selected dependent profile not found.")
            dep_id = str(dep.id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    ext = os.path.splitext(file.filename or ".pdf")[1].lower()

    def _write_temp():
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            return tmp.name

    tmp_path = await asyncio.to_thread(_write_temp)

    job_id = await create_job(str(current_user.id), session=db)
    client_host = request.client.host if request.client else "unknown"

    background_tasks.add_task(
        process_upload_background,
        job_id=job_id,
        tmp_path=tmp_path,
        filename=file.filename or "report.pdf",
        user_id=str(current_user.id),
        dependent_id=dep_id,
        chat_id=chat_id,
        client_host=client_host,
    )

    return UploadJobResponse(
        job_id=job_id,
        status_url=f"/upload/status/{job_id}",
    )


@router.get("/upload/status/{job_id}", response_model=UploadStatusResponse, tags=["PDF Upload"])
async def upload_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(job_id, session=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")

    return UploadStatusResponse(
        job_id=job_id,
        status=job["status"],
        document_id=job.get("document_id"),
        error=job.get("error"),
    )
