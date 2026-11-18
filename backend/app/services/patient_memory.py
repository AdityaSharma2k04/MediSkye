import asyncio
import logging
import uuid
from typing import Any

import numpy as np
from app.core.config import settings
from app.db.models import Chat, ChatChunk, ChatDocument, Document, PatientFact
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    a = np.array(vec1, dtype=float)
    b = np.array(vec2, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def get_active_facts(
    user_id: Any,
    dependent_id: Any | None,
    session: AsyncSession,
    limit: int = 25,
) -> dict[str, list[PatientFact]]:
    """
    Retrieve active patient facts ordered by:
    (is_user_verified DESC, confidence DESC, last_seen_at DESC)
    Grouped by fact_type.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id

    critical_types = ("allergy", "medication", "condition")
    dep_filter = PatientFact.dependent_id == d_id if d_id else PatientFact.dependent_id.is_(None)
    base_filter = [
        PatientFact.user_id == u_id,
        dep_filter,
        PatientFact.is_active.is_(True),
        PatientFact.confidence >= settings.PATIENT_MEMORY_MIN_CONFIDENCE,
    ]

    # Safety-critical facts first (allergies, medications, conditions)
    critical_query = (
        select(PatientFact)
        .filter(
            *base_filter,
            func.lower(PatientFact.fact_type).in_(critical_types),
        )
        .order_by(
            PatientFact.is_user_verified.desc(),
            PatientFact.confidence.desc(),
            PatientFact.last_seen_at.desc(),
        )
        .limit(limit)
    )
    crit_res = await session.execute(critical_query)
    critical_facts = list(crit_res.scalars().all())

    # Remaining limit for other categories
    remaining_limit = max(0, limit - len(critical_facts))
    other_facts = []
    if remaining_limit > 0:
        other_query = (
            select(PatientFact)
            .filter(
                *base_filter,
                func.lower(PatientFact.fact_type).notin_(critical_types),
            )
            .order_by(
                PatientFact.is_user_verified.desc(),
                PatientFact.confidence.desc(),
                PatientFact.last_seen_at.desc(),
            )
            .limit(remaining_limit)
        )
        other_res = await session.execute(other_query)
        other_facts = list(other_res.scalars().all())

    facts = critical_facts + other_facts

    # Resolve source document names for facts if linked to a chat or document
    chat_uuids = []
    doc_uuids = []
    for f in facts:
        if "[Source Report:" not in f.fact_text and f.source_id:
            try:
                sid_uuid = uuid.UUID(str(f.source_id))
                if getattr(f, "source_type", None) == "pdf":
                    doc_uuids.append(sid_uuid)
                else:
                    chat_uuids.append(sid_uuid)
            except (ValueError, TypeError):
                pass

    doc_name_by_id = {}
    if doc_uuids:
        d_res = await session.execute(select(Document).filter(Document.id.in_(doc_uuids)))
        for d in d_res.scalars().all():
            doc_name_by_id[d.id] = d.filename or d.title

    chat_doc_map = {}
    if chat_uuids:
        # Check direct chat.document_id
        c_res = await session.execute(
            select(Chat.id, Document.filename, Document.title)
            .join(Document, Chat.document_id == Document.id)
            .filter(Chat.id.in_(chat_uuids))
        )
        for row in c_res.all():
            chat_doc_map[row[0]] = row[1] or row[2]

        # Check ChatDocument join
        cd_res = await session.execute(
            select(ChatDocument.chat_id, Document.filename, Document.title)
            .join(Document, ChatDocument.document_id == Document.id)
            .filter(ChatDocument.chat_id.in_(chat_uuids))
        )
        for row in cd_res.all():
            if row[0] not in chat_doc_map:
                chat_doc_map[row[0]] = row[1] or row[2]

    for f in facts:
        if "[Source Report:" not in f.fact_text and f.source_id:
            try:
                sid_uuid = uuid.UUID(str(f.source_id))
                resolved_name = doc_name_by_id.get(sid_uuid) or chat_doc_map.get(sid_uuid)
                if resolved_name:
                    f.source_doc_name = resolved_name
            except (ValueError, TypeError):
                pass

    grouped: dict[str, list[PatientFact]] = {}
    for f in facts:
        ft = f.fact_type.lower()
        if ft not in grouped:
            grouped[ft] = []
        grouped[ft].append(f)

    return grouped


async def get_relevant_past_chunks(
    query: str,
    user_id: Any,
    dependent_id: Any | None,
    exclude_chat_id: Any | None,
    session: AsyncSession,
    k: int = 5,
) -> list[ChatChunk]:
    """
    Retrieve top-k semantically relevant ChatChunks from past sessions via cosine similarity.
    Excludes the current chat_id.
    """
    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
    c_exclude = uuid.UUID(str(exclude_chat_id)) if (exclude_chat_id and isinstance(exclude_chat_id, str)) else exclude_chat_id

    from sqlalchemy.orm import selectinload

    stmt = (
        select(ChatChunk)
        .options(selectinload(ChatChunk.chat).selectinload(Chat.document))
        .filter(
            ChatChunk.user_id == u_id,
            ChatChunk.dependent_id == d_id if d_id else ChatChunk.dependent_id.is_(None),
        )
    )
    if c_exclude:
        stmt = stmt.filter(ChatChunk.chat_id != c_exclude)

    stmt = stmt.order_by(ChatChunk.created_at.desc()).limit(100)
    result = await session.execute(stmt)
    chunks = result.scalars().all()

    if not chunks:
        return []

    final_chunks: list[ChatChunk] = []

    if not query or not query.strip():
        final_chunks = list(chunks[:k])
    else:
        embedder = None
        try:
            from app.rag.embedder import get_embedder
            embedder = get_embedder()
        except Exception as e:
            logger.warning("Embedder not available for past chunk retrieval: %s", e)

        if not embedder:
            final_chunks = list(chunks[:k])
        else:
            try:
                query_vec = await asyncio.to_thread(embedder.embed_query, query)
                MIN_SIM = 0.50
                scored = []
                for chunk in chunks:
                    if chunk.embedding:
                        sim = _cosine_similarity(query_vec, chunk.embedding)
                        if sim >= MIN_SIM:
                            scored.append((sim, chunk))

                scored.sort(key=lambda x: x[0], reverse=True)
                final_chunks = [chunk for _, chunk in scored[:k]]
            except Exception as e:
                logger.error("Cosine similarity matching failed: %s", e)
                final_chunks = []

    # Annotate chunks with associated document and session details
    if final_chunks:
        chat_ids = [c.chat_id for c in final_chunks if c.chat_id]
        if chat_ids:
            try:
                # 1. Fetch Chats
                c_res = await session.execute(select(Chat).filter(Chat.id.in_(chat_ids)))
                chats_by_id = {c.id: c for c in c_res.scalars().all()}

                # 2. Check direct Document links
                doc_ids = [c.document_id for c in chats_by_id.values() if c.document_id]
                docs_by_id = {}
                if doc_ids:
                    d_res = await session.execute(select(Document).filter(Document.id.in_(doc_ids)))
                    for d in d_res.scalars().all():
                        docs_by_id[d.id] = d

                # 3. Check ChatDocument join table
                cd_res = await session.execute(
                    select(ChatDocument.chat_id, Document)
                    .join(Document, ChatDocument.document_id == Document.id)
                    .filter(ChatDocument.chat_id.in_(chat_ids))
                )
                cd_docs = {}
                for row in cd_res.all():
                    cd_docs[row[0]] = row[1]

                for chunk in final_chunks:
                    chat_obj = chats_by_id.get(chunk.chat_id)
                    doc_obj = None
                    if chat_obj and chat_obj.document_id:
                        doc_obj = docs_by_id.get(chat_obj.document_id)
                    if not doc_obj and chunk.chat_id in cd_docs:
                        doc_obj = cd_docs[chunk.chat_id]

                    if doc_obj:
                        chunk.source_doc_name = doc_obj.filename or doc_obj.title
                        chunk.source_doc_date = doc_obj.created_at
                    if chat_obj:
                        chunk.source_session_title = chat_obj.session_title
                        chunk.source_chat_date = chat_obj.created_at or chunk.created_at
            except Exception as annot_err:
                logger.warning("Error annotating past chunks with document names: %s", annot_err)

    return final_chunks


async def get_chat_documents(
    chat_id: Any,
    session: AsyncSession,
) -> list[Document]:
    """
    Retrieve all documents associated with a chat session (via ChatDocument or legacy Chat.document_id).
    """
    if not chat_id:
        return []

    c_id = uuid.UUID(str(chat_id)) if isinstance(chat_id, str) else chat_id

    # 1. Many-to-many joined documents
    stmt = (
        select(Document)
        .join(ChatDocument, ChatDocument.document_id == Document.id)
        .filter(ChatDocument.chat_id == c_id)
        .order_by(ChatDocument.added_at.asc())
    )
    res = await session.execute(stmt)
    docs = list(res.scalars().all())

    # 2. Check legacy single-document link on Chat
    chat_res = await session.execute(select(Chat).filter(Chat.id == c_id))
    chat = chat_res.scalars().first()
    if chat and chat.document_id:
        doc_res = await session.execute(select(Document).filter(Document.id == chat.document_id))
        legacy_doc = doc_res.scalars().first()
        if legacy_doc and not any(d.id == legacy_doc.id for d in docs):
            docs.append(legacy_doc)

    return docs
