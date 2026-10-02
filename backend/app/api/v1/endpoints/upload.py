import os
import tempfile
import uuid
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import User, Document, DependentProfile
from app.schemas.upload import UploadResponse
from app.services.pdf_service import validate_file_upload
from app.rag.loader import PDFExtractionError, extract_text_from_file
from app.core.audit import log_audit
from app.rag.retriever import create_hybrid_index

router = APIRouter()


@router.post("/upload", response_model=UploadResponse, tags=["PDF Upload"])
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
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
            dep_id = dep.id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id format.")

    # Create Document record in DB
    doc = Document(
        user_id=current_user.id,
        dependent_id=dep_id,
        filename=file.filename or "report.pdf",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # If active chat_id provided, link document to active chat session via ChatDocument
    if chat_id:
        try:
            c_uuid = uuid.UUID(chat_id)
            from app.db.models import ChatDocument, Chat
            chat_res = await db.execute(
                select(Chat).filter(Chat.id == c_uuid, Chat.user_id == current_user.id)
            )
            chat_obj = chat_res.scalars().first()
            if chat_obj:
                cd = ChatDocument(chat_id=chat_obj.id, document_id=doc.id)
                db.add(cd)
                await db.commit()
        except (ValueError, Exception):
            pass

    tmp_path = None
    try:
        ext = os.path.splitext(file.filename or ".pdf")[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        page_docs = await extract_text_from_file(tmp_path, file.filename or "report.pdf")
        
        has_xray = any(d.metadata.get("type") == "xray" for d in page_docs)
        if has_xray:
            await log_audit(db, "XRAY_ANALYSIS", current_user.id, "upload", request.client.host, dependent_id=dep_id)
            
        await log_audit(db, "PDF_UPLOADED", current_user.id, f"doc_{doc.id}", request.client.host, dependent_id=dep_id)

        # Create hybrid index (FAISS + BM25) and save to disk
        index_dir = settings.BASE_DIR / "indexes"
        index_dir.mkdir(exist_ok=True)
        index_path = str(index_dir / f"user_{current_user.id}_doc_{doc.id}.index")
        
        vectorstore, bm25_index, chunks = create_hybrid_index(page_docs, index_path)


        # Update DB with file_path
        doc.file_path = index_path
        await db.commit()

        return UploadResponse(message="PDF uploaded and processed successfully.", document_id=str(doc.id))
    except PDFExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
