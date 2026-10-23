import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.db.models import Chat, Document, ChatDocument
from app.core.auth import UserDTO, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat Multi-Document"])


@router.get("/chats/{chat_id}/documents", response_model=List[Dict[str, Any]])
async def get_chat_documents_endpoint(
    chat_id: UUID,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all documents attached to a specific chat session.
    """
    chat_res = await db.execute(
        select(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = chat_res.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")

    stmt = (
        select(Document)
        .join(ChatDocument, ChatDocument.document_id == Document.id)
        .filter(ChatDocument.chat_id == chat_id, Document.user_id == current_user.id)
        .order_by(ChatDocument.added_at.asc())
    )
    res = await db.execute(stmt)
    docs = list(res.scalars().all())

    # Include legacy linked doc if not already present
    if chat.document_id and not any(d.id == chat.document_id for d in docs):
        leg_res = await db.execute(
            select(Document).filter(Document.id == chat.document_id, Document.user_id == current_user.id)
        )
        leg_doc = leg_res.scalars().first()
        if leg_doc:
            docs.append(leg_doc)

    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "title": d.title or d.filename,
            "file_path": d.file_path,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.post("/chats/{chat_id}/documents/{doc_id}")
async def attach_document_to_chat(
    chat_id: UUID,
    doc_id: UUID,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach an existing document to a chat session.
    """
    chat_res = await db.execute(
        select(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = chat_res.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")

    doc_res = await db.execute(
        select(Document).filter(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Check if already attached
    cd_res = await db.execute(
        select(ChatDocument).filter(
            ChatDocument.chat_id == chat_id,
            ChatDocument.document_id == doc_id,
        )
    )
    existing_link = cd_res.scalars().first()
    if not existing_link:
        new_link = ChatDocument(chat_id=chat_id, document_id=doc_id)
        db.add(new_link)
        await db.commit()

    return {
        "status": "attached",
        "chat_id": str(chat_id),
        "document_id": str(doc_id),
        "filename": doc.filename,
    }


@router.delete("/chats/{chat_id}/documents/{doc_id}")
async def detach_document_from_chat(
    chat_id: UUID,
    doc_id: UUID,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Detach a document from a chat session. Does NOT delete the document or physical file.
    """
    chat_res = await db.execute(
        select(Chat).filter(Chat.id == chat_id, Chat.user_id == current_user.id)
    )
    chat = chat_res.scalars().first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")

    cd_res = await db.execute(
        select(ChatDocument).filter(
            ChatDocument.chat_id == chat_id,
            ChatDocument.document_id == doc_id,
        )
    )
    link = cd_res.scalars().first()
    if link:
        await db.delete(link)

    # If chat had this as its primary document_id, nullify it
    if chat.document_id == doc_id:
        chat.document_id = None
        db.add(chat)

    await db.commit()

    return {
        "status": "detached",
        "chat_id": str(chat_id),
        "document_id": str(doc_id),
    }
