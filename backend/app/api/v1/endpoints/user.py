import asyncio
import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from uuid import UUID

import firebase_admin
import firebase_admin.auth
from app.core.audit import log_audit
from app.core.auth import (
    UserDTO,
    evict_token_cache_for_user,
    get_current_user,
    get_current_user_full,
    get_password_hash,
    verify_password,
)
from app.core.clinical import compute_bmi_info
from app.core.limiter import limiter
from app.core.security import clean_filename_to_title, sanitize_text
from app.db.database import get_db
from app.db.models import (
    AuditLog,
    Chat,
    ChatChunk,
    ChatDocument,
    DependentProfile,
    Document,
    PatientFact,
    UploadJob,
    User,
)
from app.rag.index_storage import adelete_index_artifacts
from app.schemas.dependent import DependentCreate, DependentResponse, DependentUpdate
from app.schemas.user import (
    DocumentResponse,
    MemoryConsentRequest,
    PasswordChange,
    PatientFactCreate,
    PatientFactResponse,
    PatientFactUpdate,
    ReassignDocumentPatientRequest,
    RenameDocumentRequest,
    RenameSessionRequest,
    UserResponse,
    UserUpdate,
)
from app.services.clinical_units import check_is_future_date, normalize_clinical_unit
from app.services.patient_service import calculate_age
from app.services.upload_jobs import purge_expired_sample_documents
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import defer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users & Dependents"])

@router.get("/users/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user_full)):
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    user_res.bmi_info = compute_bmi_info(current_user.height_cm, current_user.weight_kg)
    return user_res

@router.put("/users/me", response_model=UserResponse)
@router.patch("/users/me", response_model=UserResponse)
async def update_user_me(
    request: Request,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db)
):
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    evict_token_cache_for_user(current_user.id)
    
    await log_audit(db, "PROFILE_UPDATE", current_user.id, "profile", request.client.host if request.client else "unknown")
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    user_res.bmi_info = compute_bmi_info(current_user.height_cm, current_user.weight_kg)
    return user_res


# DEPRECATED: Password changes are now managed directly via Firebase Auth.
# Kept for backward compatibility with legacy clients and tests.
@router.post("/users/me/password", deprecated=True)
@limiter.limit("5/minute")
async def change_password(
    body: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db),
):
    """
    DEPRECATED: Password changes are now managed directly via Firebase Auth.
    Change the current user's password after verifying their existing password.
    """
    valid = await asyncio.to_thread(verify_password, body.current_password, current_user.hashed_password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = await asyncio.to_thread(get_password_hash, body.new_password)
    current_user.token_invalid_before = datetime.now(UTC)
    db.add(current_user)
    await db.commit()
    evict_token_cache_for_user(current_user.id)
    await log_audit(db, "PASSWORD_CHANGED", current_user.id, "change_password", request.client.host if request.client else "unknown")
    return {"message": "Password changed successfully"}

@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    request: Request,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user.id
    user_email = current_user.email
    await log_audit(db, "USER_DELETION_REQUESTED", user_id, "account", request.client.host if request.client else "unknown")
    
    docs = await db.execute(select(Document).filter(Document.user_id == user_id))
    for doc in docs.scalars().all():
        if doc.file_path:
            await adelete_index_artifacts(doc.file_path)

    doc_ids_subq = select(Document.id).filter(Document.user_id == user_id)
    chat_ids_subq = select(Chat.id).filter(Chat.user_id == user_id)
    await db.execute(
        ChatDocument.__table__.delete().where(
            (ChatDocument.document_id.in_(doc_ids_subq)) | (ChatDocument.chat_id.in_(chat_ids_subq))
        )
    )
    await db.execute(ChatChunk.__table__.delete().where(ChatChunk.user_id == user_id))
    await db.execute(PatientFact.__table__.delete().where(PatientFact.user_id == user_id))
    await db.execute(UploadJob.__table__.delete().where(UploadJob.user_id == user_id))
    await db.execute(Chat.__table__.delete().where(Chat.user_id == user_id))
    await db.execute(Document.__table__.delete().where(Document.user_id == user_id))
    await db.execute(DependentProfile.__table__.delete().where(DependentProfile.user_id == user_id))
    
    await db.delete(current_user)
    await db.commit()
    evict_token_cache_for_user(user_id)
    try:
        import time as _time

        from app.core.redis_client import redis_client
        await redis_client.setex(f"user_revoked_at:{user_email.lower().strip()}", 3600, str(_time.time()))
    except Exception as rev_err:
        logger.debug("Could not record user_revoked_at in redis_client: %s", rev_err)

    try:
        fb_user = await asyncio.to_thread(firebase_admin.auth.get_user_by_email, user_email)
        await asyncio.to_thread(firebase_admin.auth.delete_user, fb_user.uid)
        logger.info("firebase_delete_ok user_id=%s", user_id)
    except firebase_admin.auth.UserNotFoundError:
        logger.warning("firebase_user_not_found user_id=%s", user_id)
    except Exception as e:
        logger.error("firebase_delete_failed user_id=%s error=%s", user_id, e)


# ==========================================
# User Documents & History Endpoints
# ==========================================

@router.get("/users/me/documents", response_model=list[DocumentResponse])
async def get_my_documents(
    patient_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await purge_expired_sample_documents(db, current_user.id)
    query = (
        select(Document)
        .options(
            defer(Document.extracted_text),
            defer(Document.cached_summary),
            defer(Document.cached_metrics),
        )
        .filter(Document.user_id == current_user.id)
    )
    if patient_id is not None and str(patient_id).strip():
        pid_clean = str(patient_id).strip().lower()
        if pid_clean == "self":
            query = query.filter(Document.dependent_id.is_(None))
        else:
            try:
                dep_uuid = uuid.UUID(str(patient_id).strip())
            except ValueError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == dep_uuid,
                    DependentProfile.user_id == current_user.id
                )
            )
            if not dep_res.scalars().first():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            query = query.filter(Document.dependent_id == dep_uuid)

    query = query.order_by(Document.created_at.desc())
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_path": doc.file_path,
            "title": doc.title or clean_filename_to_title(doc.filename),
            "collected_at": doc.collected_at,
            "is_future_collection_date": check_is_future_date(doc.collected_at),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "dependent_id": str(doc.dependent_id) if doc.dependent_id else None
        }
        for doc in docs
    ]


@router.patch("/users/me/documents/{document_id}/title", tags=["Documents", "Users & Dependents"])
async def rename_user_document_title(
    document_id: str,
    body: RenameDocumentRequest,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename a document's title (auth-gated to document owner)."""
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID.")

    result = await db.execute(
        select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found or access denied.")

    doc.title = sanitize_text(body.title).strip()
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"id": str(doc.id), "title": doc.title}


@router.patch("/users/me/documents/{document_id}/patient", tags=["Documents", "Users & Dependents"])
async def reassign_user_document_patient(
    document_id: str,
    body: ReassignDocumentPatientRequest,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Document profiles are permanently locked after upload.
    Reassignment is forbidden.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Document profile is permanently locked after upload.",
    )


@router.get("/users/me/chats")
async def get_general_chats(
    document_id: str | None = None,
    session_id: str | None = None,
    patient_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await purge_expired_sample_documents(db, current_user.id)
    query = select(Chat).filter(Chat.user_id == current_user.id)
    if document_id:
        try:
            d_uuid = uuid.UUID(document_id)
            query = query.filter(Chat.document_id == d_uuid)
        except ValueError:
            pass
    if session_id:
        query = query.filter(Chat.session_id == session_id)

    if patient_id is not None and str(patient_id).strip():
        pid_clean = str(patient_id).strip().lower()
        if pid_clean == "self":
            query = query.filter(Chat.dependent_id.is_(None))
        else:
            try:
                dep_uuid = uuid.UUID(str(patient_id).strip())
            except ValueError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == dep_uuid,
                    DependentProfile.user_id == current_user.id
                )
            )
            if not dep_res.scalars().first():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            query = query.filter(Chat.dependent_id == dep_uuid)

    query = query.order_by(Chat.created_at.asc())
    result = await db.execute(query)
    chats = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "session_id": c.session_id or (f"doc-{c.document_id}" if c.document_id else f"legacy-{c.user_id}"),
            "session_title": c.session_title,
            "document_id": str(c.document_id) if c.document_id else None,
            "role": c.role,
            "message": c.message,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "timestamp": c.created_at.isoformat() if c.created_at else None,
            "dependent_id": str(c.dependent_id) if c.dependent_id else None,
        }
        for c in chats
    ]

@router.get("/users/me/documents/{document_id}/chats")
async def get_document_chats(
    document_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")
        
    doc_res = await db.execute(
        select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
    )
    if not doc_res.scalars().first():
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(Chat)
        .filter(Chat.user_id == current_user.id, Chat.document_id == doc_uuid)
        .order_by(Chat.created_at.asc())
    )
    chats = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "session_id": c.session_id or f"doc-{doc_uuid}",
            "session_title": c.session_title,
            "document_id": str(c.document_id) if c.document_id else str(doc_uuid),
            "role": c.role,
            "message": c.message,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "timestamp": c.created_at.isoformat() if c.created_at else None,
            "dependent_id": str(c.dependent_id) if c.dependent_id else None,
        }
        for c in chats
    ]


@router.get("/users/me/chats/sessions")
async def get_user_chat_sessions(
    patient_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await purge_expired_sample_documents(db, current_user.id)
    query = select(Chat.session_id, Chat.session_title).filter(
        Chat.user_id == current_user.id, Chat.session_id.is_not(None)
    )
    if patient_id is not None and str(patient_id).strip():
        pid_clean = str(patient_id).strip().lower()
        if pid_clean == "self":
            query = query.filter(Chat.dependent_id.is_(None))
        else:
            try:
                dep_uuid = uuid.UUID(str(patient_id).strip())
            except ValueError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == dep_uuid,
                    DependentProfile.user_id == current_user.id
                )
            )
            if not dep_res.scalars().first():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent not found")
            query = query.filter(Chat.dependent_id == dep_uuid)

    res = await db.execute(query.distinct())
    rows = res.all()
    return [{"session_id": r[0], "title": r[1]} for r in rows]


@router.patch("/users/me/chats/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: RenameSessionRequest,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Allow renaming a conversation session (auth-gated to session owner)."""
    title = sanitize_text(body.title).strip()
    res = await db.execute(
        select(Chat).filter(Chat.user_id == current_user.id, Chat.session_id == session_id)
    )
    chats = res.scalars().all()
    if not chats:
        try:
            doc_uuid = uuid.UUID(session_id)
            doc_res = await db.execute(
                select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
            )
            doc = doc_res.scalars().first()
            if doc:
                doc.title = title
                db.add(doc)
                await db.commit()
                return {"session_id": session_id, "title": title}
        except ValueError:
            pass
        raise HTTPException(status_code=404, detail="Chat session not found.")

    for c in chats:
        c.session_title = title
        db.add(c)

    doc_ids = {c.document_id for c in chats if c.document_id}
    if doc_ids:
        docs_res = await db.execute(
            select(Document).filter(Document.id.in_(doc_ids), Document.user_id == current_user.id)
        )
        for d in docs_res.scalars().all():
            d.title = title
            db.add(d)

    await db.commit()
    return {"session_id": session_id, "title": title, "session_title": title}


async def _resolve_patient_scope(
    db: AsyncSession,
    user_id: UUID,
    patient_id: str | None = None,
    dependent_id: str | None = None,
) -> UUID | None:
    """
    Resolves patient/dependent scope.
    Returns:
      None -> primary user ('self')
      UUID -> verified dependent UUID belonging to user_id
    Raises:
      HTTPException(400) if raw id is invalid UUID
      HTTPException(404) if dependent does not exist or belong to user_id
    """
    raw_id = patient_id if patient_id is not None else dependent_id
    if raw_id is None:
        return None
    val = str(raw_id).strip()
    if not val or val.lower() in ("self", "none", "", str(user_id).lower()):
        return None
    try:
        dep_uuid = UUID(val)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid dependent_id.")

    res = await db.execute(
        select(DependentProfile.id).filter(
            DependentProfile.id == dep_uuid,
            DependentProfile.user_id == user_id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependent profile not found.")
    return dep_uuid


@router.delete("/users/me/chats/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all chats in a session and cascade delete extracted patient facts and documents."""
    target_doc_uuid: UUID | None = None
    if session_id.startswith("doc-"):
        try:
            target_doc_uuid = uuid.UUID(session_id[4:])
        except ValueError:
            pass
    else:
        try:
            target_doc_uuid = uuid.UUID(session_id)
        except ValueError:
            pass

    chat_query = select(Chat).filter(Chat.user_id == current_user.id)
    if target_doc_uuid:
        chat_query = chat_query.filter(
            or_(
                Chat.session_id == session_id,
                Chat.session_id == f"doc-{target_doc_uuid}",
                Chat.document_id == target_doc_uuid,
            )
        )
    else:
        chat_query = chat_query.filter(Chat.session_id == session_id)

    res = await db.execute(chat_query)
    chats = res.scalars().all()

    target_doc = None
    if target_doc_uuid:
        doc_res = await db.execute(
            select(Document).filter(
                Document.id == target_doc_uuid,
                Document.user_id == current_user.id,
            )
        )
        target_doc = doc_res.scalars().first()

    if not chats and not target_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found.")

    chat_ids = [c.id for c in chats]
    chat_id_strs = [str(cid) for cid in chat_ids]

    source_ids_to_delete = {str(session_id), *chat_id_strs}
    if target_doc:
        source_ids_to_delete.add(str(target_doc.id))
        source_ids_to_delete.add(f"doc-{target_doc.id}")

    # CASCADE DELETE EXTRACTED INSIGHTS: Physically delete PatientFact rows matching session_id, chat_ids, or doc_id
    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            PatientFact.source_id.in_(list(source_ids_to_delete)),
        )
    )

    # Delete child links first
    if chat_ids:
        await db.execute(delete(ChatChunk).where(ChatChunk.chat_id.in_(chat_ids)))
        await db.execute(delete(ChatDocument).where(ChatDocument.chat_id.in_(chat_ids)))
        await db.execute(delete(Chat).where(Chat.id.in_(chat_ids)))

    if target_doc:
        if target_doc.file_path:
            await adelete_index_artifacts(target_doc.file_path)
        try:
            from app.rag.retriever import evict_index_cache
            evict_index_cache(str(target_doc.id))
            if target_doc.file_path:
                evict_index_cache(str(target_doc.file_path))
        except Exception as ev_err:
            logger.debug("Could not evict index cache for doc %s: %s", target_doc.id, ev_err)

        try:
            from app.core.config import settings
            session_cache = settings.VECTOR_CACHE_DIR / str(target_doc.id)
            if session_cache.is_dir():
                shutil.rmtree(session_cache, ignore_errors=True)
        except Exception as e:
            logger.error("Error removing vector cache for doc %s: %s", target_doc.id, e)

        await db.execute(delete(ChatDocument).where(ChatDocument.document_id == target_doc.id))
        await db.execute(
            delete(UploadJob).where(
                UploadJob.user_id == current_user.id,
                UploadJob.document_id == str(target_doc.id),
            )
        )
        await db.delete(target_doc)

    await db.commit()


@router.delete("/users/me/chats", status_code=status.HTTP_200_OK)
async def clear_all_chats(
    patient_id: str | None = None,
    dependent_id: str | None = None,
    clear_patient_context: bool = True,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Clear all chats (both standalone and document-linked), documents, upload jobs,
    vector index artifacts, patient facts, and wipe stored clinical profile context.
    """
    raw_scope = patient_id if patient_id is not None else dependent_id
    is_unscoped = (raw_scope is None or str(raw_scope).strip().lower() in ("all", "*", ""))
    scoped_dep_id: UUID | None = None
    if not is_unscoped:
        scoped_dep_id = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)

    # 1. Query matching documents
    doc_query = select(Document).filter(Document.user_id == current_user.id)
    if not is_unscoped:
        if scoped_dep_id is None:
            doc_query = doc_query.filter(Document.dependent_id.is_(None))
        else:
            doc_query = doc_query.filter(Document.dependent_id == scoped_dep_id)

    doc_res = await db.execute(doc_query)
    target_docs = doc_res.scalars().all()
    doc_ids = [d.id for d in target_docs]
    doc_id_strs = [str(d) for d in doc_ids]

    # Clean up FAISS / BM25 index artifacts, index cache and vector cache
    from app.core.config import settings
    from app.rag.retriever import evict_index_cache

    for doc in target_docs:
        if doc.file_path:
            try:
                await adelete_index_artifacts(doc.file_path)
            except Exception as e:
                logger.warning("Failed deleting index artifacts for doc %s: %s", doc.id, e)
        try:
            evict_index_cache(str(doc.id))
            if doc.file_path:
                evict_index_cache(str(doc.file_path))
        except Exception:
            pass
        try:
            session_cache = settings.VECTOR_CACHE_DIR / str(doc.id)
            if session_cache.is_dir():
                shutil.rmtree(session_cache, ignore_errors=True)
        except Exception:
            pass

    # 2. Query matching chats
    chat_query = select(Chat.id).filter(Chat.user_id == current_user.id)
    if not is_unscoped:
        if scoped_dep_id is None:
            conds = [Chat.dependent_id.is_(None)]
            if doc_ids:
                conds.append(Chat.document_id.in_(doc_ids))
            chat_query = chat_query.filter(or_(*conds))
        else:
            conds = [Chat.dependent_id == scoped_dep_id]
            if doc_ids:
                conds.append(Chat.document_id.in_(doc_ids))
            chat_query = chat_query.filter(or_(*conds))

    chat_res = await db.execute(chat_query)
    chat_ids = chat_res.scalars().all()
    chat_id_strs = [str(cid) for cid in chat_ids]

    # 3. Delete Child Links First (Avoid FK Constraint Errors)
    cd_conds = []
    if chat_ids:
        cd_conds.append(ChatDocument.chat_id.in_(chat_ids))
    if doc_ids:
        cd_conds.append(ChatDocument.document_id.in_(doc_ids))
    if is_unscoped:
        subq_c = select(Chat.id).filter(Chat.user_id == current_user.id)
        subq_d = select(Document.id).filter(Document.user_id == current_user.id)
        cd_conds.append(ChatDocument.chat_id.in_(subq_c))
        cd_conds.append(ChatDocument.document_id.in_(subq_d))

    if cd_conds:
        await db.execute(delete(ChatDocument).where(or_(*cd_conds)))

    if is_unscoped:
        await db.execute(delete(ChatChunk).where(ChatChunk.user_id == current_user.id))
    else:
        chunk_conds = []
        if scoped_dep_id is None:
            chunk_conds.append(ChatChunk.dependent_id.is_(None))
        else:
            chunk_conds.append(ChatChunk.dependent_id == scoped_dep_id)
        if chat_ids:
            chunk_conds.append(ChatChunk.chat_id.in_(chat_ids))
        await db.execute(delete(ChatChunk).where(ChatChunk.user_id == current_user.id, or_(*chunk_conds)))

    # 4. Delete All Chats
    if chat_ids:
        await db.execute(delete(Chat).where(Chat.id.in_(chat_ids)))
    elif is_unscoped:
        await db.execute(delete(Chat).where(Chat.user_id == current_user.id))

    # 5. Delete UploadJobs & Documents
    if is_unscoped:
        await db.execute(delete(UploadJob).where(UploadJob.user_id == current_user.id))
        await db.execute(delete(Document).where(Document.user_id == current_user.id))
    else:
        if doc_id_strs:
            await db.execute(
                delete(UploadJob).where(
                    UploadJob.user_id == current_user.id,
                    UploadJob.document_id.in_(doc_id_strs),
                )
            )
        if doc_ids:
            await db.execute(delete(Document).where(Document.id.in_(doc_ids)))

    # 6. Delete Patient Facts
    if is_unscoped:
        fact_res = await db.execute(delete(PatientFact).where(PatientFact.user_id == current_user.id))
        deleted_facts_count = fact_res.rowcount
    else:
        fact_conds = []
        if scoped_dep_id is None:
            fact_conds.append(PatientFact.dependent_id.is_(None))
        else:
            fact_conds.append(PatientFact.dependent_id == scoped_dep_id)
        if chat_id_strs:
            fact_conds.append(PatientFact.source_id.in_(chat_id_strs))
        if doc_id_strs:
            fact_conds.append(PatientFact.source_id.in_(doc_id_strs))
        fact_res = await db.execute(
            delete(PatientFact).where(PatientFact.user_id == current_user.id, or_(*fact_conds))
        )
        deleted_facts_count = fact_res.rowcount

    # 7. Clear Stored Patient Profile Context
    if clear_patient_context:
        def _wipe_clinical_fields(obj):
            obj.pre_existing_conditions = None
            obj.current_medications = None
            obj.known_allergies = None
            obj.blood_type = None
            obj.diet_type = None
            obj.activity_level = None
            obj.occupation = None
            obj.height_cm = None
            obj.weight_kg = None

        if is_unscoped or scoped_dep_id is None:
            user_res = await db.execute(select(User).filter(User.id == current_user.id))
            user_obj = user_res.scalars().first()
            if user_obj:
                _wipe_clinical_fields(user_obj)
                db.add(user_obj)

        if is_unscoped:
            dep_res = await db.execute(select(DependentProfile).filter(DependentProfile.user_id == current_user.id))
            for dep in dep_res.scalars().all():
                _wipe_clinical_fields(dep)
                db.add(dep)
        elif scoped_dep_id is not None:
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == scoped_dep_id,
                    DependentProfile.user_id == current_user.id,
                )
            )
            dep_obj = dep_res.scalars().first()
            if dep_obj:
                _wipe_clinical_fields(dep_obj)
                db.add(dep_obj)

        evict_token_cache_for_user(current_user.id)

    await db.commit()

    return {
        "status": "success",
        "deleted_chats": len(chat_ids),
        "deleted_documents": len(doc_ids),
        "deleted_facts": deleted_facts_count,
        "patient_context_cleared": clear_patient_context,
    }


@router.delete("/users/me/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete("/chats/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_single_chat(
    chat_id: UUID,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single chat turn and any associated facts."""
    chat = await db.get(Chat, chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat message not found.")

    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            PatientFact.source_id.in_([str(chat_id), str(chat.session_id)]),
        )
    )
    await db.execute(delete(ChatChunk).where(ChatChunk.chat_id == chat_id))
    await db.execute(delete(ChatDocument).where(ChatDocument.chat_id == chat_id))
    await db.delete(chat)
    await db.commit()


def _normalize_cached_metrics(cached) -> list[dict]:
    """Normalize Document.cached_metrics into a plain list of dicts with standardized units."""
    if cached is None:
        return []
    if isinstance(cached, str):
        try:
            cached = json.loads(cached)
        except Exception:
            return []
    if isinstance(cached, dict) and "metrics" in cached:
        cached = cached["metrics"]
    if not isinstance(cached, list):
        return []
    metrics = []
    for item in cached:
        d = None
        if isinstance(item, dict):
            d = dict(item)
        elif hasattr(item, "model_dump"):
            d = item.model_dump()
        if d is not None:
            if d.get("unit"):
                d["unit"] = normalize_clinical_unit(d["unit"])
            metrics.append(d)
    return metrics


@router.get("/users/me/export-data", tags=["Users & Dependents"])
async def export_my_data(
    request: Request,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db)
):
    """
    Export all user account data as a clean JSON bundle:
    decrypted profile, dependent_profiles, remembered_facts,
    and documents (with lab_metrics and chat history).
    """
    profile_data = {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "date_of_birth": current_user.date_of_birth.isoformat() if current_user.date_of_birth else None,
        "calculated_age": calculate_age(current_user.date_of_birth),
        "biological_sex": current_user.biological_sex,
        "blood_type": current_user.blood_type,
        "pre_existing_conditions": current_user.pre_existing_conditions,
        "known_allergies": current_user.known_allergies,
        "current_medications": current_user.current_medications,
        "height_cm": current_user.height_cm,
        "weight_kg": current_user.weight_kg,
        "bmi_info": compute_bmi_info(current_user.height_cm, current_user.weight_kg),
        "diet_type": current_user.diet_type,
        "activity_level": current_user.activity_level,
        "occupation": current_user.occupation,
        "emergency_contact_name": current_user.emergency_contact_name,
        "emergency_contact_phone": current_user.emergency_contact_phone,
        "language_preference": current_user.language_preference,
        "memory_consent_granted": current_user.memory_consent_granted,
        "phi_consent_granted": current_user.phi_consent_granted,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    # Decrypted dependent profiles
    dep_res = await db.execute(
        select(DependentProfile)
        .filter(DependentProfile.user_id == current_user.id)
        .order_by(DependentProfile.created_at.asc())
    )
    dependents = dep_res.scalars().all()
    dependent_profiles_data = [
        {
            "id": str(d.id),
            "relationship": d.relationship,
            "full_name": d.full_name,
            "date_of_birth": d.date_of_birth.isoformat() if d.date_of_birth else None,
            "calculated_age": calculate_age(d.date_of_birth),
            "biological_sex": d.biological_sex,
            "blood_type": d.blood_type,
            "pre_existing_conditions": d.pre_existing_conditions,
            "known_allergies": d.known_allergies,
            "current_medications": d.current_medications,
            "height_cm": d.height_cm,
            "weight_kg": d.weight_kg,
            "bmi_info": compute_bmi_info(d.height_cm, d.weight_kg),
            "diet_type": d.diet_type,
            "activity_level": d.activity_level,
            "occupation": d.occupation,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in dependents
    ]

    # Remembered facts
    facts_res = await db.execute(
        select(PatientFact)
        .filter(PatientFact.user_id == current_user.id)
        .order_by(PatientFact.created_at.desc())
    )
    facts = facts_res.scalars().all()
    remembered_facts_data = [
        {
            "id": str(f.id),
            "fact_text": f.fact_text,
            "fact_type": f.fact_type,
            "fact_category": f.fact_type,
            "source_report_id": f.source_id,
            "dependent_id": str(f.dependent_id) if f.dependent_id else None,
            "is_active": f.is_active,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in facts
    ]

    # Documents with lab_metrics and chat history (batched chat query)
    docs_res = await db.execute(
        select(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = docs_res.scalars().all()

    chats_res = await db.execute(
        select(Chat)
        .filter(Chat.user_id == current_user.id)
        .order_by(Chat.created_at.asc())
    )
    all_chats = chats_res.scalars().all()
    chats_by_doc = {}
    standalone_chats_data = []
    for c in all_chats:
        chat_item = {
            "id": str(c.id),
            "role": c.role,
            "message": c.message,
            "session_id": c.session_id,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        if c.document_id:
            chats_by_doc.setdefault(c.document_id, []).append(chat_item)
        else:
            standalone_chats_data.append(chat_item)

    documents_data = [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "collected_at": doc.collected_at,
            "is_future_collection_date": check_is_future_date(doc.collected_at),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "dependent_id": str(doc.dependent_id) if doc.dependent_id else None,
            "cached_summary": doc.cached_summary,
            "lab_metrics": _normalize_cached_metrics(doc.cached_metrics),
            "chat_history": chats_by_doc.get(doc.id, []),
        }
        for doc in docs
    ]

    await log_audit(db, "ACCOUNT_DATA_EXPORTED", current_user.id, "export_data", request.client.host if request.client else "unknown")

    return {
        "export_timestamp": datetime.now(UTC).isoformat(),
        "account_id": str(current_user.id),
        "email": current_user.email,
        "profile": profile_data,
        "dependent_profiles": dependent_profiles_data,
        "remembered_facts": remembered_facts_data,
        "documents": documents_data,
        "standalone_chats": standalone_chats_data,
    }


@router.get("/users/me/documents/{document_id}/export")
async def export_document_data(
    document_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export a document's full chat transcript and cached lab metrics as JSON.

    Returns the document metadata, every stored chat message (user + assistant)
    in chronological order, and the cached lab metrics ([] when none extracted).
    Read-only: does not invoke LLM extraction or mutate any state.
    """
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chats_res = await db.execute(
        select(Chat)
        .filter(Chat.user_id == current_user.id, Chat.document_id == doc_uuid)
        .order_by(Chat.created_at.asc())
    )
    chats = chats_res.scalars().all()

    return {
        "document": {
            "id": str(doc.id),
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "collected_at": doc.collected_at,
            "is_future_collection_date": check_is_future_date(doc.collected_at),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "dependent_id": str(doc.dependent_id) if doc.dependent_id else None,
        },
        "messages": [
            {
                "id": str(c.id),
                "role": c.role,
                "message": c.message,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chats
        ],
        "lab_metrics": _normalize_cached_metrics(doc.cached_metrics),
    }

@router.delete("/users/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_document(
    document_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    result = await db.execute(
        select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.file_path:
        await adelete_index_artifacts(doc.file_path)

    try:
        from app.rag.retriever import evict_index_cache
        evict_index_cache(str(doc.id))
        if doc.file_path:
            evict_index_cache(str(doc.file_path))
    except Exception as ev_err:
        logger.debug("Could not evict index cache for doc %s: %s", doc.id, ev_err)

    # Clean up vector cache session directory if present
    try:
        from app.core.config import settings
        session_cache = settings.VECTOR_CACHE_DIR / str(doc.id)
        if session_cache.is_dir():
            shutil.rmtree(session_cache, ignore_errors=True)
    except Exception as e:
        logger.error("Error removing vector cache for doc %s: %s", doc.id, e)

    chat_res = await db.execute(
        select(Chat).filter(Chat.user_id == current_user.id, Chat.document_id == doc.id)
    )
    primary_chats = chat_res.scalars().all()

    chats_to_delete = []
    for c in primary_chats:
        cd_res = await db.execute(
            select(ChatDocument.document_id).filter(
                ChatDocument.chat_id == c.id,
                ChatDocument.document_id != doc.id,
            )
        )
        other_docs = cd_res.scalars().all()
        if other_docs:
            c.document_id = other_docs[0]
            db.add(c)
        else:
            chats_to_delete.append(c.id)

    chat_id_strs = [str(cid) for cid in chats_to_delete]
    fact_conditions = [
        PatientFact.source_id == str(doc.id),
        PatientFact.source_id == f"doc-{doc.id}",
    ]
    if chat_id_strs:
        fact_conditions.append(PatientFact.source_id.in_(chat_id_strs))

    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            or_(*fact_conditions)
        )
    )

    await db.execute(
        delete(UploadJob).where(
            UploadJob.user_id == current_user.id,
            UploadJob.document_id == str(doc.id),
        )
    )
    await db.execute(ChatDocument.__table__.delete().where(ChatDocument.document_id == doc.id))
    if chats_to_delete:
        await db.execute(ChatChunk.__table__.delete().where(ChatChunk.chat_id.in_(chats_to_delete)))
        await db.execute(Chat.__table__.delete().where(Chat.id.in_(chats_to_delete)))

    await db.delete(doc)
    await db.commit()

# ==========================================
# Dependent Profile Endpoints (Caregiver Mode)
# ==========================================

@router.get("/users/me/dependents", response_model=list[DependentResponse])
async def list_dependents(
    request: Request,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DependentProfile)
        .filter(DependentProfile.user_id == current_user.id)
        .order_by(DependentProfile.created_at.asc())
    )
    dependents = result.scalars().all()
    
    responses = []
    for dep in dependents:
        item = DependentResponse.model_validate(dep)
        item.calculated_age = calculate_age(dep.date_of_birth)
        item.bmi_info = compute_bmi_info(dep.height_cm, dep.weight_kg)
        responses.append(item)
        
    return responses

@router.post("/users/me/dependents", response_model=DependentResponse, status_code=status.HTTP_201_CREATED)
async def create_dependent(
    request: Request,
    dependent_in: DependentCreate,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    dep = DependentProfile(
        user_id=current_user.id,
        relationship=dependent_in.relationship,
        full_name=dependent_in.full_name,
        date_of_birth=dependent_in.date_of_birth,
        biological_sex=dependent_in.biological_sex,
        blood_type=dependent_in.blood_type,
        pre_existing_conditions=dependent_in.pre_existing_conditions,
        known_allergies=dependent_in.known_allergies,
        current_medications=dependent_in.current_medications,
        height_cm=dependent_in.height_cm,
        weight_kg=dependent_in.weight_kg,
        diet_type=dependent_in.diet_type,
        activity_level=dependent_in.activity_level,
        occupation=dependent_in.occupation,
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    
    await log_audit(db, "DEPENDENT_CREATED", current_user.id, "dependent", request.client.host if request.client else "unknown", dependent_id=dep.id)
    
    item = DependentResponse.model_validate(dep)
    item.calculated_age = calculate_age(dep.date_of_birth)
    item.bmi_info = compute_bmi_info(dep.height_cm, dep.weight_kg)
    return item

@router.put("/users/me/dependents/{dependent_id}", response_model=DependentResponse)
async def update_dependent(
    dependent_id: UUID,
    request: Request,
    dependent_in: DependentUpdate,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DependentProfile).filter(
            DependentProfile.id == dependent_id,
            DependentProfile.user_id == current_user.id
        )
    )
    dep = result.scalars().first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependent profile not found.")
        
    update_data = dependent_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(dep, key, value)
        
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    
    await log_audit(db, "DEPENDENT_UPDATED", current_user.id, "dependent", request.client.host if request.client else "unknown", dependent_id=dep.id)
    
    item = DependentResponse.model_validate(dep)
    item.calculated_age = calculate_age(dep.date_of_birth)
    item.bmi_info = compute_bmi_info(dep.height_cm, dep.weight_kg)
    return item

@router.delete("/users/me/dependents/{dependent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dependent(
    dependent_id: UUID,
    request: Request,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DependentProfile).filter(
            DependentProfile.id == dependent_id,
            DependentProfile.user_id == current_user.id
        )
    )
    dep = result.scalars().first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependent profile not found.")

    # 1. Query all dependent documents
    doc_res = await db.execute(
        select(Document).filter(
            Document.user_id == current_user.id,
            Document.dependent_id == dependent_id
        )
    )
    dep_docs = doc_res.scalars().all()
    dep_doc_ids = [d.id for d in dep_docs]

    # 2. Purge local and GCS index artifacts & vector cache
    from app.core.config import settings
    from app.rag.retriever import evict_index_cache

    for d in dep_docs:
        if d.file_path:
            try:
                await adelete_index_artifacts(d.file_path)
            except Exception as e:
                logger.warning("Failed deleting index artifacts for dependent doc %s: %s", d.id, e)
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

    # 3. Find and purge all chats associated with these documents or directly with dependent
    chats_to_purge = set()
    dep_chats_res = await db.execute(
        select(Chat.id).filter(
            Chat.user_id == current_user.id,
            Chat.dependent_id == dependent_id
        )
    )
    for cid in dep_chats_res.scalars().all():
        chats_to_purge.add(cid)

    if dep_doc_ids:
        c_res = await db.execute(
            select(Chat.id).filter(
                Chat.user_id == current_user.id,
                Chat.document_id.in_(dep_doc_ids)
            )
        )
        for cid in c_res.scalars().all():
            chats_to_purge.add(cid)

        cd_chats_res = await db.execute(
            select(ChatDocument.chat_id).filter(
                ChatDocument.document_id.in_(dep_doc_ids)
            )
        )
        for cid in cd_chats_res.scalars().all():
            chats_to_purge.add(cid)

    # Cascade-delete chat chunks, chat documents, and chats
    if chats_to_purge:
        purge_list = list(chats_to_purge)
        await db.execute(delete(ChatChunk).where(ChatChunk.chat_id.in_(purge_list)))
        await db.execute(delete(ChatDocument).where(ChatDocument.chat_id.in_(purge_list)))
        await db.execute(delete(Chat).where(Chat.id.in_(purge_list)))

    # Delete any chat chunks directly linked to dependent_id
    await db.execute(delete(ChatChunk).where(ChatChunk.dependent_id == dependent_id))

    # Delete ChatDocuments for these documents
    if dep_doc_ids:
        await db.execute(delete(ChatDocument).where(ChatDocument.document_id.in_(dep_doc_ids)))

    # Delete PatientFacts linked to dependent_id or doc IDs
    fact_conds = [PatientFact.dependent_id == dependent_id]
    if dep_doc_ids:
        fact_conds.append(PatientFact.source_id.in_([str(did) for did in dep_doc_ids]))
    if chats_to_purge:
        fact_conds.append(PatientFact.source_id.in_([str(cid) for cid in chats_to_purge]))

    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            or_(*fact_conds)
        )
    )

    # Delete the documents & upload jobs
    if dep_doc_ids:
        await db.execute(
            delete(UploadJob).where(
                UploadJob.user_id == current_user.id,
                UploadJob.document_id.in_([str(did) for did in dep_doc_ids]),
            )
        )
        await db.execute(delete(Document).where(Document.id.in_(dep_doc_ids)))

    # Set dependent_id = None on any audit logs to prevent FK constraint error when deleting dep
    await db.execute(
        update(AuditLog).where(AuditLog.dependent_id == dep.id).values(dependent_id=None)
    )
    await log_audit(db, "DEPENDENT_DELETED", current_user.id, "dependent", request.client.host if request.client else "unknown")
    await db.delete(dep)
    await db.commit()


# ==========================================
# Patient Memory & Facts Endpoints
# ==========================================

@router.post("/users/me/memory/consent")
@router.post("/memory/consent")
@router.patch("/users/me/memory-consent")
async def update_memory_consent(
    request: Request,
    body: MemoryConsentRequest,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable long-term memory extraction and cross-session personalization."""
    current_user.memory_consent_granted = body.consent
    if not body.consent:
        await db.execute(delete(ChatChunk).where(ChatChunk.user_id == current_user.id))
        if getattr(body, "clear_existing", False):
            await db.execute(delete(PatientFact).where(PatientFact.user_id == current_user.id))
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    evict_token_cache_for_user(current_user.id)
    try:
        await log_audit(
            db,
            "MEMORY_CONSENT_GRANTED" if body.consent else "MEMORY_CONSENT_REVOKED",
            current_user.id,
            "memory_consent",
            request.client.host if request.client else "unknown",
        )
    except Exception as audit_err:
        logger.warning("Failed to log audit event for memory consent: %s", audit_err)
    return {
        "status": "success",
        "memory_consent_granted": current_user.memory_consent_granted,
    }


@router.get("/users/me/memory/status")
@router.get("/memory/status")
async def get_memory_status(
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current memory consent status and total number of remembered facts for the user or dependent."""
    dep_uuid = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)
    filters = [
        PatientFact.user_id == current_user.id,
        PatientFact.is_active.is_(True),
    ]
    if dep_uuid is None:
        filters.append(PatientFact.dependent_id.is_(None))
    else:
        filters.append(PatientFact.dependent_id == dep_uuid)

    res = await db.execute(select(func.count(PatientFact.id)).filter(*filters))
    fact_count = int(res.scalar() or 0)
    return {
        "memory_consent_granted": current_user.memory_consent_granted,
        "fact_count": fact_count,
    }


@router.get("/users/me/facts", response_model=list[PatientFactResponse])
@router.get("/users/me/memory/facts", response_model=list[PatientFactResponse])
@router.get("/memory/facts", response_model=list[PatientFactResponse])
async def get_user_facts(
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all active structured health facts remembered for the user or dependent."""
    dep_uuid = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)
    filters = [
        PatientFact.user_id == current_user.id,
        PatientFact.is_active.is_(True),
    ]
    if dep_uuid is None:
        filters.append(PatientFact.dependent_id.is_(None))
    else:
        filters.append(PatientFact.dependent_id == dep_uuid)

    res = await db.execute(
        select(PatientFact)
        .filter(*filters)
        .order_by(
            PatientFact.is_user_verified.desc(),
            PatientFact.confidence.desc(),
            PatientFact.last_seen_at.desc(),
        )
    )
    facts = res.scalars().all()

    chat_ids = []
    for f in facts:
        if f.source_id:
            try:
                chat_ids.append(UUID(str(f.source_id)))
            except ValueError:
                pass

    chat_to_doc = {}
    direct_doc_ids = set()
    if chat_ids:
        # Check if source_id matches a Chat with a document_id
        c_res = await db.execute(
            select(Chat.id, Chat.document_id).filter(
                Chat.id.in_(chat_ids),
                Chat.document_id.is_not(None),
            )
        )
        for c_id, d_id in c_res.all():
            if d_id:
                chat_to_doc[str(c_id)] = str(d_id)

        # Check if source_id is directly a Document id
        d_res = await db.execute(
            select(Document.id).filter(
                Document.id.in_(chat_ids),
                Document.user_id == current_user.id,
            )
        )
        for (d_id,) in d_res.all():
            direct_doc_ids.add(str(d_id))

    result = []
    for f in facts:
        resp = PatientFactResponse.model_validate(f)
        s_id_str = str(f.source_id) if f.source_id else None
        if s_id_str and s_id_str in chat_to_doc:
            resp.source_document_id = chat_to_doc[s_id_str]
        elif s_id_str and s_id_str in direct_doc_ids:
            resp.source_document_id = s_id_str
        result.append(resp)
    return result


@router.post("/users/me/facts", response_model=PatientFactResponse, status_code=status.HTTP_201_CREATED)
async def create_user_fact(
    body: PatientFactCreate,
    request: Request,
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a health fact for the current user or their dependent."""
    raw_id = body.patient_id or (str(body.dependent_id) if body.dependent_id else None) or patient_id or dependent_id
    dep_uuid = await _resolve_patient_scope(db, current_user.id, raw_id)

    now = datetime.now(UTC)
    new_fact = PatientFact(
        user_id=current_user.id,
        dependent_id=dep_uuid,
        fact_type=body.fact_type,
        fact_text=body.fact_text,
        confidence=body.confidence if body.confidence is not None else 1.0,
        is_active=True,
        is_user_verified=True,
        source_type=body.source_type or "user_edit",
        source_id=None,
        source_excerpt=body.source_excerpt,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
    )
    db.add(new_fact)
    await db.commit()
    await db.refresh(new_fact)

    await log_audit(db, "FACT_CREATED_MANUAL", current_user.id, f"fact_{new_fact.id}", request.client.host if request.client else "unknown")
    return PatientFactResponse.model_validate(new_fact)


@router.patch("/users/me/facts/{fact_id}", response_model=PatientFactResponse)
async def update_user_fact(
    fact_id: UUID,
    body: PatientFactUpdate,
    request: Request,
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a specific remembered health fact (auth-gated, cross-user returns 404)."""
    filters = [
        PatientFact.id == fact_id,
        PatientFact.user_id == current_user.id,
    ]
    raw_id = patient_id if patient_id is not None else dependent_id
    if raw_id is not None:
        dep_uuid = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)
        if dep_uuid is None:
            filters.append(PatientFact.dependent_id.is_(None))
        else:
            filters.append(PatientFact.dependent_id == dep_uuid)

    res = await db.execute(select(PatientFact).filter(*filters))
    fact = res.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    update_data = body.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(fact, field, val)

    fact.last_seen_at = datetime.now(UTC)
    db.add(fact)
    await db.commit()
    await db.refresh(fact)

    await log_audit(db, "FACT_UPDATED", current_user.id, f"fact_{fact_id}", request.client.host if request.client else "unknown")
    return PatientFactResponse.model_validate(fact)


@router.delete("/users/me/facts/{fact_id}")
@router.delete("/users/me/memory/facts/{fact_id}")
@router.delete("/memory/facts/{fact_id}")
async def delete_memory_fact(
    fact_id: UUID,
    request: Request,
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete a specific remembered health fact (auth-gated, cross-user returns 404)."""
    filters = [
        PatientFact.id == fact_id,
        PatientFact.user_id == current_user.id,
    ]
    raw_id = patient_id if patient_id is not None else dependent_id
    if raw_id is not None:
        dep_uuid = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)
        if dep_uuid is None:
            filters.append(PatientFact.dependent_id.is_(None))
        else:
            filters.append(PatientFact.dependent_id == dep_uuid)

    res = await db.execute(select(PatientFact).filter(*filters))
    fact = res.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    await db.delete(fact)
    await db.commit()
    await log_audit(db, "FACT_DELETED", current_user.id, f"fact_{fact_id}", request.client.host if request.client else "unknown")
    return {"message": "Fact deleted successfully", "id": str(fact_id)}


@router.delete("/users/me/memory/facts")
@router.delete("/memory/facts")
async def clear_all_memory_facts(
    request: Request,
    patient_id: str | None = None,
    dependent_id: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete all remembered health facts for the user or dependent."""
    dep_uuid = await _resolve_patient_scope(db, current_user.id, patient_id, dependent_id)
    if dep_uuid is None:
        filters = [PatientFact.user_id == current_user.id, PatientFact.dependent_id.is_(None)]
    else:
        filters = [PatientFact.user_id == current_user.id, PatientFact.dependent_id == dep_uuid]

    res = await db.execute(select(PatientFact).filter(*filters))
    facts = res.scalars().all()
    count = len(facts)
    for f in facts:
        await db.delete(f)
    await db.commit()
    await log_audit(db, "ALL_FACTS_CLEARED", current_user.id, "memory", request.client.host if request.client else "unknown")
    return {"message": "All memory facts cleared successfully", "count": count}

