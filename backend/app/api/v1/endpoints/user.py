import uuid
import logging
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
from pathlib import Path
import shutil
import os
from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import User, DependentProfile, Document, Chat, PatientFact
from app.core.auth import get_current_user, verify_password, get_password_hash
from app.schemas.user import (
    UserResponse,
    UserUpdate,
    PasswordChange,
    MemoryConsentRequest,
    PatientFactResponse,
    PatientFactCreate,
    PatientFactUpdate,
)
from app.schemas.dependent import DependentCreate, DependentUpdate, DependentResponse
from app.core.audit import log_audit
from app.core.limiter import limiter
from app.services.patient_service import calculate_age

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Users & Dependents"])

@router.get("/users/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    return user_res

@router.put("/users/me", response_model=UserResponse)
@router.patch("/users/me", response_model=UserResponse)
async def update_user_me(
    request: Request,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    await log_audit(db, "PROFILE_UPDATE", current_user.id, "profile", request.client.host if request.client else "unknown")
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    return user_res


@router.post("/users/me/password")
@limiter.limit("5/minute")
async def change_password(
    body: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password after verifying their existing password."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = get_password_hash(body.new_password)
    await db.commit()
    await log_audit(db, "PASSWORD_CHANGED", current_user.id, "change_password", request.client.host if request.client else "unknown")
    return {"message": "Password changed successfully"}

@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await log_audit(db, "USER_DELETION_REQUESTED", current_user.id, "account", request.client.host if request.client else "unknown")
    
    docs = await db.execute(select(Document).filter(Document.user_id == current_user.id))
    for doc in docs.scalars().all():
        if doc.file_path:
            # Delete FAISS index directory if it exists
            try:
                if os.path.exists(doc.file_path):
                    shutil.rmtree(doc.file_path)
            except Exception as e:
                logger.error("Error removing physical files for doc %s: %s", doc.id, e)
                
            # Delete corresponding BM25 index pickle file even if FAISS directory was missing
            try:
                bm25_path = Path(doc.file_path).parent / f"{Path(doc.file_path).stem}_bm25.pkl"
                os.remove(bm25_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                logger.error("Error removing BM25 index for doc %s: %s", doc.id, e)
                
    await db.execute(Chat.__table__.delete().where(Chat.user_id == current_user.id))
    await db.execute(Document.__table__.delete().where(Document.user_id == current_user.id))
    await db.execute(DependentProfile.__table__.delete().where(DependentProfile.user_id == current_user.id))
    
    await db.delete(current_user)
    await db.commit()
    return None

# ==========================================
# User Documents & History Endpoints
# ==========================================

@router.get("/users/me/documents")
async def get_my_documents(
    current_user: User = Depends(get_current_user),
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
            "title": doc.title,  # nullable — frontend uses filename fallback
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "dependent_id": str(doc.dependent_id) if doc.dependent_id else None
        }
        for doc in docs
    ]

@router.get("/users/me/documents/{document_id}/chats")
async def get_document_chats(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")
        
    result = await db.execute(
        select(Chat)
        .filter(Chat.user_id == current_user.id, Chat.document_id == doc_uuid)
        .order_by(Chat.created_at.asc())
    )
    chats = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "role": c.role,
            "message": c.message,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in chats
    ]

@router.delete("/users/me/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
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
        # Delete FAISS index directory if it exists
        try:
            if os.path.exists(doc.file_path):
                if os.path.isdir(doc.file_path):
                    shutil.rmtree(doc.file_path)
                else:
                    os.remove(doc.file_path)
        except Exception as e:
            logger.error("Error removing physical files for doc %s: %s", doc.id, e)

        # Delete corresponding BM25 index pickle file even if FAISS directory was missing
        try:
            bm25_path = Path(doc.file_path).parent / f"{Path(doc.file_path).stem}_bm25.pkl"
            os.remove(bm25_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error("Error removing BM25 index for doc %s: %s", doc.id, e)

    # Clean up vector cache session directory if present
    try:
        from app.core.config import settings
        session_cache = settings.VECTOR_CACHE_DIR / str(doc.id)
        if session_cache.is_dir():
            shutil.rmtree(session_cache, ignore_errors=True)
    except Exception as e:
        logger.error("Error removing vector cache for doc %s: %s", doc.id, e)

    await db.execute(Chat.__table__.delete().where(Chat.document_id == doc.id, Chat.user_id == current_user.id))
    await db.delete(doc)
    await db.commit()
    return None

# ==========================================
# Dependent Profile Endpoints (Caregiver Mode)
# ==========================================

@router.get("/users/me/dependents", response_model=List[DependentResponse])
async def list_dependents(
    request: Request,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
        
    await log_audit(db, "DEPENDENT_DELETED", current_user.id, "dependent", request.client.host if request.client else "unknown", dependent_id=dep.id)
    await db.delete(dep)
    await db.commit()
    return None


# ==========================================
# Patient Memory & Facts Endpoints
# ==========================================

@router.post("/users/me/memory/consent")
@router.post("/memory/consent")
async def update_memory_consent(
    request: Request,
    body: MemoryConsentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable long-term memory extraction and cross-session personalization."""
    current_user.memory_consent_granted = body.consent
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    await log_audit(
        db,
        "MEMORY_CONSENT_GRANTED" if body.consent else "MEMORY_CONSENT_REVOKED",
        current_user.id,
        "memory_consent",
        request.client.host if request.client else "unknown",
    )
    return {
        "status": "success",
        "memory_consent_granted": current_user.memory_consent_granted,
    }


@router.get("/users/me/memory/status")
@router.get("/memory/status")
async def get_memory_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current memory consent status and total number of remembered facts."""
    res = await db.execute(
        select(PatientFact).filter(
            PatientFact.user_id == current_user.id,
            PatientFact.is_active == True,
        )
    )
    facts = res.scalars().all()
    return {
        "memory_consent_granted": current_user.memory_consent_granted,
        "fact_count": len(facts),
    }


@router.get("/users/me/facts", response_model=List[PatientFactResponse])
@router.get("/users/me/memory/facts", response_model=List[PatientFactResponse])
@router.get("/memory/facts", response_model=List[PatientFactResponse])
async def get_user_facts(
    dependent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
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
            pass
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
    return [PatientFactResponse.model_validate(f) for f in facts]


@router.post("/users/me/facts", response_model=PatientFactResponse, status_code=status.HTTP_201_CREATED)
async def create_user_fact(
    body: PatientFactCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a specific remembered health fact (auth-gated, cross-user returns 404)."""
    res = await db.execute(
        select(PatientFact).filter(
            PatientFact.id == fact_id,
            PatientFact.user_id == current_user.id,
        )
    )
    fact = res.scalars().first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found.")

    fact.is_active = False
    fact.last_seen_at = datetime.now(UTC)
    await db.commit()
    await log_audit(db, "FACT_DELETED", current_user.id, f"fact_{fact_id}", request.client.host if request.client else "unknown")
    return {"message": "Fact deleted successfully", "id": str(fact_id)}


@router.delete("/users/me/memory/facts")
@router.delete("/memory/facts")
async def clear_all_memory_facts(
    request: Request,
    dependent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete all remembered health facts for the user or dependent."""
    filters = [PatientFact.user_id == current_user.id]
    if dependent_id:
        try:
            dep_uuid = UUID(dependent_id)
            filters.append(PatientFact.dependent_id == dep_uuid)
        except ValueError:
            pass

    res = await db.execute(select(PatientFact).filter(*filters))
    facts = res.scalars().all()
    for f in facts:
        f.is_active = False
    await db.commit()
    await log_audit(db, "ALL_FACTS_CLEARED", current_user.id, "memory", request.client.host if request.client else "unknown")
    return {"message": "All memory facts cleared successfully", "count": len(facts)}

