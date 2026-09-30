import uuid
from typing import List
from uuid import UUID
from pathlib import Path
import shutil
import os
from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import User, DependentProfile, Document, Chat
from app.core.auth import get_current_user
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.dependent import DependentCreate, DependentUpdate, DependentResponse
from app.core.audit import log_audit
from app.services.patient_service import calculate_age

router = APIRouter(tags=["Users & Dependents"])

@router.get("/users/me", response_model=UserResponse)
async def read_user_me(current_user: User = Depends(get_current_user)):
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    return user_res

@router.put("/users/me", response_model=UserResponse)
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
    
    await log_audit(db, "PROFILE_UPDATE", current_user.id, "profile", request.client.host)
    user_res = UserResponse.model_validate(current_user)
    user_res.calculated_age = calculate_age(current_user.date_of_birth)
    return user_res

@router.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await log_audit(db, "USER_DELETION_REQUESTED", current_user.id, "account", request.client.host)
    
    docs = await db.execute(select(Document).filter(Document.user_id == current_user.id))
    for doc in docs.scalars().all():
        if doc.file_path:
            # Delete FAISS index directory if it exists
            try:
                if os.path.exists(doc.file_path):
                    shutil.rmtree(doc.file_path)
            except Exception as e:
                print(f"Error removing physical files for doc {doc.id}: {e}")
                
            # Delete corresponding BM25 index pickle file even if FAISS directory was missing
            try:
                bm25_path = Path(doc.file_path).parent / f"{Path(doc.file_path).stem}_bm25.pkl"
                os.remove(bm25_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Error removing BM25 index for doc {doc.id}: {e}")
                
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
        
    await log_audit(db, "DEPENDENTS_LIST_ACCESSED", current_user.id, "dependents", request.client.host)
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
    )
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    
    await log_audit(db, "DEPENDENT_CREATED", current_user.id, "dependent", request.client.host, dependent_id=dep.id)
    
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
    
    await log_audit(db, "DEPENDENT_UPDATED", current_user.id, "dependent", request.client.host, dependent_id=dep.id)
    
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
        
    await log_audit(db, "DEPENDENT_DELETED", current_user.id, "dependent", request.client.host, dependent_id=dep.id)
    await db.delete(dep)
    await db.commit()
    return None
