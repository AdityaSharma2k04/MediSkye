import uuid
import json
import shutil
import asyncio
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
import firebase_admin
import firebase_admin.auth
from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy import func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import User, DependentProfile, Document, Chat, ChatDocument, PatientFact, ChatChunk, UploadJob
from app.core.auth import (
    UserDTO,
    get_current_user,
    get_current_user_full,
    evict_token_cache_for_user,
    verify_password,
    get_password_hash,
)
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    PasswordChange,
    MemoryConsentRequest,
    RenameSessionRequest,
    PatientFactResponse,
    PatientFactCreate,
    PatientFactUpdate,
    DocumentResponse,
    RenameDocumentRequest,
)
from app.schemas.dependent import DependentCreate, DependentUpdate, DependentResponse
from app.core.audit import log_audit
from app.core.limiter import limiter
from app.rag.prompt_builder import build_document_summary_prompt
from app.core.security import clean_filename_to_title, sanitize_text
from app.services.patient_service import calculate_age
from app.services.clinical_units import normalize_clinical_unit, check_is_future_date
from app.rag.index_storage import adelete_index_artifacts

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users & Dependents"])

@router.get("/users/me", response_model=UserResponse)
async def read_user_me(current_user: UserDTO = Depends(get_current_user)):
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
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
        from app.core.redis_client import redis_client
        import time as _time
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

    return None

# ==========================================
# User Documents & History Endpoints
# ==========================================

@router.get("/users/me/documents", response_model=List[DocumentResponse])
async def get_my_documents(
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
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


@router.get("/users/me/chats")
async def get_general_chats(
    document_id: Optional[str] = None,
    session_id: Optional[str] = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(Chat).filter(Chat.user_id == current_user.id)
    if document_id:
        try:
            d_uuid = uuid.UUID(document_id)
            query = query.filter(Chat.document_id == d_uuid)
        except ValueError:
            pass
    if session_id:
        query = query.filter(Chat.session_id == session_id)

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
            "dependent_id": None,
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
            "dependent_id": None,
        }
        for c in chats
    ]


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


@router.delete("/users/me/chats/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all chats in a session and cascade delete extracted patient facts."""
    res = await db.execute(
        select(Chat).filter(Chat.user_id == current_user.id, Chat.session_id == session_id)
    )
    chats = res.scalars().all()
    if not chats:
        try:
            doc_uuid = uuid.UUID(session_id)
            doc_check = await db.execute(
                select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
            )
            if doc_check.scalars().first():
                return await delete_my_document(session_id, current_user, db)
        except ValueError:
            pass
        raise HTTPException(status_code=404, detail="Chat session not found.")

    chat_ids = [c.id for c in chats]
    chat_id_strs = [str(cid) for cid in chat_ids]

    # CASCADE DELETE EXTRACTED INSIGHTS: Physically delete PatientFact rows where source_id in chat_ids
    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            PatientFact.source_id.in_(chat_id_strs),
        )
    )

    await db.execute(delete(ChatChunk).where(ChatChunk.chat_id.in_(chat_ids)))
    await db.execute(delete(ChatDocument).where(ChatDocument.chat_id.in_(chat_ids)))
    await db.execute(delete(Chat).where(Chat.id.in_(chat_ids)))
    await db.commit()
    return None


@router.delete("/users/me/chats", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_chats(
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear all standalone chats and cascade delete associated patient facts."""
    res = await db.execute(
        select(Chat.id).filter(Chat.user_id == current_user.id, Chat.document_id.is_(None))
    )
    chat_ids = res.scalars().all()
    if chat_ids:
        chat_id_strs = [str(cid) for cid in chat_ids]
        await db.execute(
            delete(PatientFact).where(
                PatientFact.user_id == current_user.id,
                PatientFact.source_id.in_(chat_id_strs),
            )
        )
        await db.execute(delete(ChatChunk).where(ChatChunk.chat_id.in_(chat_ids)))
        await db.execute(delete(ChatDocument).where(ChatDocument.chat_id.in_(chat_ids)))
        await db.execute(delete(Chat).where(Chat.id.in_(chat_ids)))
        await db.commit()
    return None


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
            PatientFact.source_id == str(chat_id),
        )
    )
    await db.execute(delete(ChatChunk).where(ChatChunk.chat_id == chat_id))
    await db.execute(delete(ChatDocument).where(ChatDocument.chat_id == chat_id))
    await db.delete(chat)
    await db.commit()
    return None


def _normalize_cached_metrics(cached) -> List[dict]:
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
            if "unit" in d and d["unit"]:
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
            "diet_type": d.diet_type,
            "activity_level": d.activity_level,
            "occupation": d.occupation,
            "emergency_contact_name": d.emergency_contact_name,
            "emergency_contact_phone": d.emergency_contact_phone,
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
            "fact_category": f.fact_category,
            "source_report_id": f.source_id,
            "dependent_id": str(f.dependent_id) if f.dependent_id else None,
            "is_active": f.is_active,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in facts
    ]

    # Documents with lab_metrics and chat history
    docs_res = await db.execute(
        select(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    docs = docs_res.scalars().all()
    documents_data = []
    for doc in docs:
        chats_res = await db.execute(
            select(Chat)
            .filter(Chat.user_id == current_user.id, Chat.document_id == doc.id)
            .order_by(Chat.created_at.asc())
        )
        chats = chats_res.scalars().all()
        chat_history = [
            {
                "id": str(c.id),
                "role": c.role,
                "message": c.message,
                "session_id": c.session_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chats
        ]
        documents_data.append({
            "id": str(doc.id),
            "filename": doc.filename,
            "title": doc.title or doc.filename,
            "collected_at": doc.collected_at,
            "is_future_collection_date": check_is_future_date(doc.collected_at),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "dependent_id": str(doc.dependent_id) if doc.dependent_id else None,
            "cached_summary": doc.cached_summary,
            "lab_metrics": _normalize_cached_metrics(doc.cached_metrics),
            "chat_history": chat_history,
        })

    # Standalone chats
    standalone_chats_res = await db.execute(
        select(Chat)
        .filter(Chat.user_id == current_user.id, Chat.document_id.is_(None))
        .order_by(Chat.created_at.asc())
    )
    standalone_chats_data = [
        {
            "id": str(c.id),
            "role": c.role,
            "message": c.message,
            "session_id": c.session_id,
            "session_title": c.session_title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in standalone_chats_res.scalars().all()
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
    fact_conditions = [PatientFact.source_id == str(doc.id)]
    if chat_id_strs:
        fact_conditions.append(PatientFact.source_id.in_(chat_id_strs))

    await db.execute(
        delete(PatientFact).where(
            PatientFact.user_id == current_user.id,
            or_(*fact_conditions)
        )
    )

    await db.execute(ChatDocument.__table__.delete().where(ChatDocument.document_id == doc.id))
    if chats_to_delete:
        await db.execute(ChatChunk.__table__.delete().where(ChatChunk.chat_id.in_(chats_to_delete)))
        await db.execute(Chat.__table__.delete().where(Chat.id.in_(chats_to_delete)))

    await db.delete(doc)
    await db.commit()
    return None

# ==========================================
# Dependent Profile Endpoints (Caregiver Mode)
# ==========================================

@router.get("/users/me/dependents", response_model=List[DependentResponse])
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
        responses.append(item)
        
    await log_audit(db, "DEPENDENTS_LIST_ACCESSED", current_user.id, "dependents", request.client.host if request.client else "unknown")
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
    from app.rag.retriever import evict_index_cache
    from app.core.config import settings

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

    # 3. Find and purge all chats associated with these documents
    chats_to_purge = set()
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

    # Delete the documents
    if dep_doc_ids:
        await db.execute(delete(Document).where(Document.id.in_(dep_doc_ids)))
        
    await log_audit(db, "DEPENDENT_DELETED", current_user.id, "dependent", request.client.host if request.client else "unknown", dependent_id=dep.id)
    await db.delete(dep)
    await db.commit()
    return None


# ==========================================
# Patient Memory & Facts Endpoints
# ==========================================

@router.post("/users/me/memory/consent")
@router.post("/memory/consent")
@router.post("/users/me/memory/consent")
@router.patch("/users/me/memory-consent")
async def update_memory_consent(
    request: Request,
    body: MemoryConsentRequest,
    current_user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable long-term memory extraction and cross-session personalization."""
    current_user.memory_consent_granted = body.consent
    if not body.consent and getattr(body, "clear_existing", False):
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
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current memory consent status and total number of remembered facts."""
    res = await db.execute(
        select(func.count(PatientFact.id)).filter(
            PatientFact.user_id == current_user.id,
            PatientFact.is_active.is_(True),
        )
    )
    fact_count = int(res.scalar() or 0)
    return {
        "memory_consent_granted": current_user.memory_consent_granted,
        "fact_count": fact_count,
    }


@router.get("/users/me/facts", response_model=List[PatientFactResponse])
@router.get("/users/me/memory/facts", response_model=List[PatientFactResponse])
@router.get("/memory/facts", response_model=List[PatientFactResponse])
async def get_user_facts(
    dependent_id: Optional[str] = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all active structured health facts remembered for the user or dependent."""
    filters = [
        PatientFact.user_id == current_user.id,
        PatientFact.is_active.is_(True),
    ]
    if dependent_id:
        try:
            dep_uuid = UUID(dependent_id)
            filters.append(PatientFact.dependent_id == dep_uuid)
        except ValueError:
            logger.debug("Ignoring invalid dependent_id UUID: %s", dependent_id)
    else:
        filters.append(PatientFact.dependent_id.is_(None))

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
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a health fact for the current user or their dependent."""
    dep_uuid = None
    if body.dependent_id:
        dep_res = await db.execute(
            select(DependentProfile).filter(
                DependentProfile.id == body.dependent_id,
                DependentProfile.user_id == current_user.id,
            )
        )
        dep = dep_res.scalars().first()
        if not dep:
            raise HTTPException(status_code=404, detail="Dependent profile not found.")
        dep_uuid = dep.id

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
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a specific remembered health fact (auth-gated, cross-user returns 404)."""
    res = await db.execute(
        select(PatientFact).filter(
            PatientFact.id == fact_id,
            PatientFact.user_id == current_user.id,
        )
    )
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
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete a specific remembered health fact (auth-gated, cross-user returns 404)."""
    res = await db.execute(
        select(PatientFact).filter(
            PatientFact.id == fact_id,
            PatientFact.user_id == current_user.id,
        )
    )
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
    dependent_id: Optional[str] = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete all remembered health facts for the user or dependent."""
    filters = [PatientFact.user_id == current_user.id]
    if dependent_id:
        try:
            dep_uuid = UUID(dependent_id)
            filters.append(PatientFact.dependent_id == dep_uuid)
        except ValueError:
            logger.debug("Ignoring invalid dependent_id UUID: %s", dependent_id)

    res = await db.execute(select(PatientFact).filter(*filters))
    facts = res.scalars().all()
    count = len(facts)
    for f in facts:
        await db.delete(f)
    await db.commit()
    await log_audit(db, "ALL_FACTS_CLEARED", current_user.id, "memory", request.client.host if request.client else "unknown")
    return {"message": "All memory facts cleared successfully", "count": count}

