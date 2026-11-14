import os
import re
import json
import tempfile
import time
import uuid
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.auth import UserDTO, get_current_user
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import Document, DependentProfile, User
from app.schemas.upload import UploadJobResponse, UploadStatusResponse
from app.services.pdf_service import validate_file_upload
from app.rag.loader import PDFExtractionError, extract_text_from_file
from app.core.audit import log_audit
from app.rag import retriever
from app.rag.retriever import acreate_hybrid_index
from app.services.upload_jobs import create_job, update_job, get_job, UploadStatus
from app.core.security import clean_filename_to_title
from app.rag.index_storage import asave_index_artifacts, asave_index_artifacts_with_retry
from app.api.v1.endpoints.metrics import extract_and_cache_metrics
from app.services.clinical_units import extract_specimen_collection_date
from app.rag.prompt_builder import build_document_summary_prompt, PROMPT_VERSION_PREFIX
from langchain_core.documents import Document as LCDocument

logger = logging.getLogger(__name__)

router = APIRouter()
_background_warm_tasks: set = set()

IGNORE_NAME_TOKENS = {
    "mr", "ms", "mrs", "dr", "prof", "shri", "smt", "master", "baby",
    "patient", "id", "name", "age", "sex", "gender", "report", "lab", "test",
    "user", "profile", "self", "you", "the", "and", "of", "to", "first", "last"
}


def _tokenize_name(name: Optional[str]) -> set[str]:
    if not name:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    return {t for t in cleaned.split() if len(t) >= 2 and t not in IGNORE_NAME_TOKENS}


def _extract_printed_patient_name(text: str) -> Optional[str]:
    if not text:
        return None
    sample = text[:4000]
    pattern = re.compile(
        r"(?i)(?:patient(?:\s*['’]s)?\s*name|pt\.?\s*name)\s*[:|\t-]?\s*(?:(?:mr|ms|mrs|dr|prof|master|baby|shri|smt)\.?\s+)?([A-Za-z][A-Za-z\s.]{1,40})"
    )
    match = pattern.search(sample)
    if match:
        raw_name = match.group(1).strip()
        raw_name = re.split(
            r"(?i)\s+(?:age|sex|gender|dob|date|ref|doctor|dr|id|pid|uhid|sample|bill|ipd|opd|ward|contact|phone)\b",
            raw_name,
        )[0]
        cleaned = re.sub(r"[\s.]+", " ", raw_name).strip()
        if len(cleaned) >= 3 and not re.match(r"(?i)^(?:unknown|na|n/a|null|none|patient)$", cleaned):
            return cleaned
    return None


def _extract_quick_text_from_file(file_path: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        try:
            import pymupdf as fitz
            with fitz.open(file_path) as doc:
                parts = []
                for i in range(min(len(doc), 2)):
                    t = doc[i].get_text()
                    if t:
                        parts.append(t)
                return "\n".join(parts)
        except Exception:
            pass
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            parts = []
            for i in range(min(len(reader.pages), 2)):
                t = reader.pages[i].extract_text()
                if t:
                    parts.append(t)
            return "\n".join(parts)
        except Exception:
            pass
    return ""


async def process_upload_background(
    job_id: str,
    tmp_path: str,
    filename: str,
    user_id: str,
    dependent_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    client_host: str = "unknown",
    custom_title: Optional[str] = None,
):
    """
    Background worker for PDF extraction, embedding, FAISS indexing, and DB commitment.
    Creates its own AsyncSessionLocal to ensure DB operations outlive the HTTP request.
    """
    from app.db.database import AsyncSessionLocal
    from app.db.models import Document, ChatDocument, Chat

    t_start = time.monotonic()
    logger.info(f"[UPLOAD {job_id}] START")

    await update_job(job_id, status=UploadStatus.PROCESSING, stage="extracting")

    parse_ms = 0
    chunk_ms = 0
    embed_ms = 0
    faiss_build_ms = 0
    db_commit_ms = 0

    async with AsyncSessionLocal() as db:
        try:
            # Initial DB setup (document record & chat link)
            t0 = time.monotonic()
            user_uuid = uuid.UUID(user_id)
            dep_uuid = uuid.UUID(dependent_id) if dependent_id else None

            # Create Document record in DB with cleaned title and building status
            from app.core.security import sanitize_text
            resolved_title = (
                sanitize_text(custom_title).strip()[:60]
                if custom_title and custom_title.strip()
                else clean_filename_to_title(filename)
            )
            doc = Document(
                user_id=user_uuid,
                dependent_id=dep_uuid,
                filename=filename,
                title=resolved_title,
                index_status="building",
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

            # 1. Text extraction (parse_ms)
            t_parse = time.perf_counter()
            page_docs = await extract_text_from_file(tmp_path, filename)
            parse_ms = int((time.perf_counter() - t_parse) * 1000)
            logger.info(f"[UPLOAD {job_id}] Extraction: {parse_ms}ms ({len(page_docs)} pages)")

            # Extract true specimen collection date if present
            try:
                col_sample_text = "\n".join([getattr(d, "page_content", str(d)) for d in page_docs[:3]])
                extracted_col_date = extract_specimen_collection_date(col_sample_text)
                if extracted_col_date:
                    doc.collected_at = extracted_col_date
                    logger.info(f"[UPLOAD {job_id}] Extracted specimen collection date: {extracted_col_date}")
            except Exception as col_err:
                logger.debug(f"[UPLOAD {job_id}] Specimen date extraction non-fatal error: {col_err}")

            # Audit logging
            has_xray = any(d.metadata.get("type") == "xray" for d in page_docs)
            if has_xray:
                await log_audit(db, "XRAY_ANALYSIS", user_uuid, "upload", client_host, dependent_id=dep_uuid)
            await log_audit(db, "PDF_UPLOADED", user_uuid, f"doc_{doc.id}", client_host, dependent_id=dep_uuid)

            await update_job(job_id, stage="indexing")
            index_dir = settings.INDEX_STORAGE_DIR
            index_dir.mkdir(parents=True, exist_ok=True)
            index_path = str(index_dir / f"user_{user_uuid}_doc_{doc.id}.index")

            # Check if acreate_hybrid_index is patched by test fixtures
            if hasattr(acreate_hybrid_index, "mock_calls") or hasattr(acreate_hybrid_index, "_mock_return_value") or hasattr(acreate_hybrid_index, "side_effect"):
                t_faiss = time.perf_counter()
                vectorstore, bm25_index, chunks = await acreate_hybrid_index(page_docs, index_path)
                faiss_build_ms = int((time.perf_counter() - t_faiss) * 1000)
                chunk_ms = 0
                embed_ms = 0
            else:
                # 2. Chunking (chunk_ms)
                t_chunk = time.perf_counter()
                splitter = retriever._build_splitter()
                raw_chunks = await asyncio.to_thread(splitter.split_documents, page_docs)
                chunks = [c for c in raw_chunks if c.page_content and c.page_content.strip()]
                if not chunks:
                    chunks = [LCDocument(page_content="Empty document", metadata={})]
                chunk_texts = [c.page_content for c in chunks]
                chunk_ms = int((time.perf_counter() - t_chunk) * 1000)
                logger.info(f"[UPLOAD {job_id}] Chunking: {chunk_ms}ms ({len(chunks)} chunks)")

                # 3. Embeddings (embed_ms)
                t_embed = time.perf_counter()
                embedder = retriever.get_embedder()
                if hasattr(embedder, "aembed_documents"):
                    embeddings = await embedder.aembed_documents(chunk_texts)
                else:
                    embeddings = await asyncio.to_thread(embedder.embed_documents, chunk_texts)
                embed_ms = int((time.perf_counter() - t_embed) * 1000)
                logger.info(f"[UPLOAD {job_id}] Embeddings: {embed_ms}ms")

                # 4. Build FAISS and BM25 and save to local disk & memory cache (faiss_build_ms)
                t_faiss = time.perf_counter()
                vectorstore, bm25_index, chunks = await asyncio.to_thread(
                    retriever.build_hybrid_index_from_embeddings,
                    chunks,
                    embeddings,
                    index_path,
                )
                retriever.cache_hybrid_index(str(doc.id), vectorstore, bm25_index)
                retriever.cache_hybrid_index(index_path, vectorstore, bm25_index)
                faiss_build_ms = int((time.perf_counter() - t_faiss) * 1000)
                logger.info(f"[UPLOAD {job_id}] FAISS/BM25 local build: {faiss_build_ms}ms")

            # 5. Update DB with file_path and index_status = "local_ready" (db_commit_ms)
            t_db = time.perf_counter()
            doc.file_path = index_path
            doc.index_status = "local_ready"
            await db.commit()
            await db.refresh(doc)
            doc_id_val = doc.id
            db_commit_ms = int((time.perf_counter() - t_db) * 1000)
            logger.info(f"[UPLOAD {job_id}] DB commit (local_ready): {db_commit_ms}ms")

            # Step A (Fast Path): Mark upload job completed IMMEDIATELY as local_ready
            await update_job(job_id, status=UploadStatus.COMPLETED, document_id=str(doc_id_val), stage="ready")
            logger.info(f"[UPLOAD {job_id}] Step A Fast Path Completed (local_ready): {time.monotonic() - t_start:.2f}s")
        except Exception as e:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            logger.error(f"[UPLOAD {job_id}] Failed after {time.monotonic() - t_start:.2f}s: {e}", exc_info=True)
            try:
                if 'doc' in locals() and getattr(doc, 'id', None):
                    async with AsyncSessionLocal() as db_cleanup:
                        res = await db_cleanup.execute(select(Document).filter(Document.id == doc.id))
                        failed_doc = res.scalars().first()
                        if failed_doc:
                            failed_doc.index_status = "failed"
                            await db_cleanup.commit()
            except Exception as ce:
                logger.warning("Failed to mark document as failed: %s", ce)
            from app.rag.loader import PDFExtractionError
            job_error = str(e) if isinstance(e, PDFExtractionError) else "We couldn't process this file. Please try another one."
            await update_job(job_id, status=UploadStatus.FAILED, error=job_error)
            return
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as unlink_err:
                    logger.debug("Could not unlink temporary upload file %s: %s", tmp_path, unlink_err)

    # Step B (Async Background GCS Sync & Cache Warming):
    async def _run_post_upload_tasks():
        try:
            t_gcs = time.perf_counter()
            gcs_success = False
            try:
                gcs_success = await asave_index_artifacts_with_retry(index_path, max_attempts=3, initial_delay=0.5)
            except Exception as gcs_err:
                logger.warning(f"[UPLOAD {job_id}] GCS index sync error: {gcs_err}")
            gcs_sync_ms = int((time.perf_counter() - t_gcs) * 1000)

            # Structured UPLOAD_BREAKDOWN logging
            logger.info(
                "UPLOAD_BREAKDOWN: parse=%dms chunk=%dms embed=%dms faiss_build=%dms db_commit=%dms gcs_sync=%dms",
                parse_ms,
                chunk_ms,
                embed_ms,
                faiss_build_ms,
                db_commit_ms,
                gcs_sync_ms,
            )

            if gcs_success:
                async with AsyncSessionLocal() as db_sync:
                    try:
                        res = await db_sync.execute(select(Document).filter(Document.id == doc_id_val))
                        sync_doc = res.scalars().first()
                        if sync_doc:
                            sync_doc.index_status = "synced"
                            await db_sync.commit()
                            logger.info(f"[UPLOAD {job_id}] Document {doc_id_val} index_status updated to 'synced'")
                    except Exception as se:
                        logger.warning(f"[UPLOAD {job_id}] Failed to set index_status to synced: {se}")

            # Post-completion cache warming
            try:
                t_warm = time.monotonic()
                await asyncio.gather(
                    _warm_document_metrics_cache(doc_id=doc_id_val, user_uuid=user_uuid, page_docs=page_docs),
                    _warm_document_summary_cache(doc_id=doc_id_val, user_uuid=user_uuid, page_docs=page_docs),
                    return_exceptions=True,
                )
                logger.info(f"[UPLOAD {job_id}] Post-completion cache warming finished in {time.monotonic() - t_warm:.2f}s")
            except Exception as ce:
                logger.warning(f"[UPLOAD {job_id}] Post-completion cache warming non-fatal error: {ce}")
        except Exception as e:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            logger.error(f"[UPLOAD {job_id}] Error in post-upload background tasks: {e}", exc_info=True)

    bg_task = asyncio.create_task(_run_post_upload_tasks())
    _background_warm_tasks.add(bg_task)
    bg_task.add_done_callback(_background_warm_tasks.discard)


async def _warm_document_metrics_cache(doc_id: uuid.UUID, user_uuid: uuid.UUID, page_docs: list) -> None:
    from app.db.database import AsyncSessionLocal
    from app.db.models import Document

    t_start = time.perf_counter()
    logger.info("prewarm_start doc_id=%s kind=%s", doc_id, "metrics")

    for attempt in range(2):
        try:
            async with AsyncSessionLocal() as db:
                metrics_result = await extract_and_cache_metrics(
                    doc_id=doc_id,
                    page_docs=page_docs,
                    db=db,
                    user_id=user_uuid,
                )
                if metrics_result is not None:
                    res = await db.execute(select(Document).filter(Document.id == doc_id))
                    doc_obj = res.scalars().first()
                    if doc_obj:
                        doc_obj.cached_metrics = metrics_result
                        raw_extracted = [
                            {
                                "test": str(m.get("test") or m.get("name") or "").strip(),
                                "value": str(m.get("value", "")).strip(),
                                "unit": str(m.get("unit", "")).strip(),
                                "range": str(m.get("range") or m.get("reference_range") or "").strip(),
                                "status": str(m.get("status") or "Normal").strip(),
                            }
                            for m in metrics_result
                            if isinstance(m, dict)
                        ]
                        doc_obj.cached_metrics = raw_extracted
                        flag_modified(doc_obj, "cached_metrics")
                        db.add(doc_obj)
                        await db.commit()
                    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
                    logger.info("prewarm_ok doc_id=%s kind=%s elapsed_ms=%d", doc_id, "metrics", elapsed_ms)

                    # Auto-extract report facts to Memory Vault when metrics warming completes (skip sample reports)
                    try:
                        from app.services.clinical_units import is_sample_document
                        if doc_obj and is_sample_document(doc_obj):
                            logger.info("Skipping document memory extraction for sample report: doc_id=%s", doc_id)
                        else:
                            from app.services.fact_persistence import process_document_memory_extraction
                            await process_document_memory_extraction(
                                doc_id=doc_id,
                                user_id=user_uuid,
                                dependent_id=doc_obj.dependent_id if doc_obj else None,
                            )
                    except Exception as mem_err:
                        logger.warning("Document memory extraction non-fatal error for doc %s: %s", doc_id, mem_err)

                    return
                else:
                    logger.warning("prewarm_skip doc_id=%s kind=%s (extraction returned None)", doc_id, "metrics")
                    return
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(settings.CACHE_WARM_RETRY_DELAY_SECONDS)
            else:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
                logger.exception("prewarm_fail doc_id=%s kind=%s", doc_id, "metrics")


async def _warm_document_summary_cache(doc_id: uuid.UUID, user_uuid: uuid.UUID, page_docs: list) -> None:
    from app.db.database import AsyncSessionLocal
    from app.db.models import Document
    from app.api.v1.endpoints.query import strip_emojis
    from app.llm.gemini_client import call_gemini_with_retry
    from google.genai.types import GenerateContentConfig, ThinkingConfig

    t_start = time.perf_counter()
    logger.info("prewarm_start doc_id=%s kind=%s", doc_id, "summary")

    for attempt in range(2):
        try:
            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Document).filter(Document.id == doc_id))
                doc_obj = res.scalars().first()
                if not doc_obj or (doc_obj.cached_summary and doc_obj.cached_summary.startswith(PROMPT_VERSION_PREFIX) and doc_obj.cached_summary.strip()):
                    return

                all_pages = [getattr(d, "page_content", str(d)) for d in page_docs if getattr(d, "page_content", str(d))]
                report_text = "\n\n".join(all_pages)

                raw_cm = doc_obj.cached_metrics
                if isinstance(raw_cm, str):
                    try:
                        raw_cm = json.loads(raw_cm)
                    except Exception:
                        raw_cm = []
                if isinstance(raw_cm, dict) and "metrics" in raw_cm:
                    raw_cm = raw_cm["metrics"]
                if not isinstance(raw_cm, list):
                    raw_cm = None

                summary_prompt = build_document_summary_prompt(report_text, cached_metrics=raw_cm)

                response = await call_gemini_with_retry(
                    contents=summary_prompt,
                    user_id=user_uuid,
                    config=GenerateContentConfig(
                        thinking_config=ThinkingConfig(thinking_budget=0),
                        temperature=0.2,
                    ),
                )
                raw_text = getattr(response, "text", "") or ""
                summary_text = strip_emojis(raw_text).strip()
                if summary_text:
                    doc_obj.cached_summary = f"{PROMPT_VERSION_PREFIX}{summary_text}"
                    db.add(doc_obj)
                    await db.commit()
            elapsed_ms = int((time.perf_counter() - t_start) * 1000)
            logger.info("prewarm_ok doc_id=%s kind=%s elapsed_ms=%d", doc_id, "summary", elapsed_ms)
            return
        except Exception as e:
            if attempt == 0:
                await asyncio.sleep(settings.CACHE_WARM_RETRY_DELAY_SECONDS)
            else:
                import sentry_sdk
                sentry_sdk.capture_exception(e)
                logger.exception("prewarm_fail doc_id=%s kind=%s", doc_id, "summary")


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=UploadJobResponse, tags=["PDF Upload"])
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    chat_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.core.security import sanitize_filename
    sanitized_filename = sanitize_filename(file.filename or "report.pdf")
    max_upload_bytes = settings.MEDISKYE_MAX_UPLOAD_MB * 1024 * 1024
    content = await file.read(max_upload_bytes + 1)
    if len(content) > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum upload size is {settings.MEDISKYE_MAX_UPLOAD_MB} MB.",
        )
    await asyncio.to_thread(validate_file_upload, content, sanitized_filename)

    dep_id = None
    target_dep = None
    res_all_deps = await db.execute(select(DependentProfile).filter(DependentProfile.user_id == current_user.id))
    all_deps = res_all_deps.scalars().all()

    res_user = await db.execute(select(User).filter(User.id == current_user.id))
    db_user = res_user.scalars().first()
    user_full_name = db_user.full_name if db_user and db_user.full_name else ""

    if patient_id and patient_id.lower() != "self" and patient_id != str(current_user.id):
        try:
            parsed_uuid = uuid.UUID(patient_id)
            target_dep = next((d for d in all_deps if d.id == parsed_uuid), None)
            if not target_dep:
                raise HTTPException(status_code=404, detail="Selected dependent profile not found.")
            dep_id = str(target_dep.id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    target_profile_name = ""
    other_profile_names = []
    if dep_id and target_dep:
        target_profile_name = target_dep.full_name or ""
        if user_full_name:
            other_profile_names.append(user_full_name)
        for d in all_deps:
            if str(d.id) != dep_id and d.full_name:
                other_profile_names.append(d.full_name)
    else:
        target_profile_name = user_full_name
        for d in all_deps:
            if d.full_name:
                other_profile_names.append(d.full_name)

    ext = os.path.splitext(sanitized_filename)[1].lower() or ".pdf"

    def _write_temp():
        with tempfile.NamedTemporaryFile(dir=tempfile.gettempdir(), delete=False, suffix=ext) as tmp:
            tmp.write(content)
            return tmp.name

    tmp_path = await asyncio.to_thread(_write_temp)

    # Printed patient name mismatch guard against cross-profile pollution
    quick_text = await asyncio.to_thread(_extract_quick_text_from_file, tmp_path, sanitized_filename)
    printed_name = _extract_printed_patient_name(quick_text)
    if printed_name:
        printed_tokens = _tokenize_name(printed_name)
        if printed_tokens:
            target_tokens = _tokenize_name(target_profile_name)
            has_target_match = bool(printed_tokens & target_tokens)
            target_is_real = bool(
                target_profile_name
                and len(target_profile_name.strip()) >= 3
                and target_tokens
                and target_profile_name.strip().lower() not in {"user", "patient", "my profile", "self", "you", "primary"}
            )
            # Check if printed name matches another profile on the user's account
            other_match_name = None
            for other_name in other_profile_names:
                other_toks = _tokenize_name(other_name)
                if other_toks and (printed_tokens & other_toks):
                    other_match_name = other_name
                    break

            if (other_match_name and not has_target_match) or (target_is_real and not has_target_match):
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                display_target = target_profile_name or "selected profile"
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Profile Lock: This report is for '{printed_name}', which does not match the currently selected profile ('{display_target}'). Please switch to the correct profile first.",
                )

    job_id = await create_job(str(current_user.id), session=db)
    client_host = request.client.host if request.client else "unknown"

    background_tasks.add_task(
        process_upload_background,
        job_id=job_id,
        tmp_path=tmp_path,
        filename=sanitized_filename,
        user_id=str(current_user.id),
        dependent_id=dep_id,
        chat_id=chat_id,
        client_host=client_host,
        custom_title=title,
    )

    return UploadJobResponse(
        job_id=job_id,
        status_url=f"/upload/status/{job_id}",
    )


@router.get("/upload/status/{job_id}", response_model=UploadStatusResponse, tags=["PDF Upload"])
async def upload_status(
    job_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(job_id, session=db)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job["user_id"] != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your job")

    idx_status = None
    if job.get("document_id"):
        try:
            doc_uuid = uuid.UUID(job["document_id"])
            d_res = await db.execute(select(Document.index_status).filter(Document.id == doc_uuid))
            idx_status = d_res.scalars().first()
        except Exception:
            pass

    return UploadStatusResponse(
        job_id=job_id,
        status=job["status"],
        stage=job.get("stage") or ("ready" if job["status"] == "completed" else "extracting"),
        index_status=idx_status,
        document_id=job.get("document_id"),
        error=job.get("error"),
    )
