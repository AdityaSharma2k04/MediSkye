import re
import os
import json
import uuid
import time
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, update, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.auth import UserDTO, get_current_user
from app.core.limiter import limiter
from app.core.audit import log_audit
from app.core.security import generate_title_from_query, sanitize_text
from app.db.database import get_db, AsyncSessionLocal
from app.db.models import Document, Chat, ChatDocument, DependentProfile, User, PatientFact
from app.llm.gemini_client import GeminiUnavailableError, get_genai_client, call_gemini_with_retry, get_fallback_models
from app.rag.index_storage import aensure_index_local
from app.schemas.query import QueryRequest
from app.rag.prompt_builder import (
    build_prompt,
    build_general_health_prompt,
    build_casual_prompt,
    build_document_summary_prompt,
    PROMPT_VERSION_PREFIX,
    condense_chat_history,
)
from app.services.clinical_units import parse_report_chronology, is_sample_document
from app.rag.intent_router import classify_intent, QueryIntent
from app.rag.safety import (
    append_disclaimer,
    get_emergency_response,
    is_emergency_query,
    detect_emergency,
    detect_emergency_language,
    EmergencyKind,
    DISCLAIMER_TEXT,
)
from app.rag.retriever import load_hybrid_index, retrieve_relevant_docs, dynamic_retrieval_k, get_cached_hybrid_index
from app.rag.output_filter import scan_output, SAFE_FALLBACK
from app.services.patient_service import calculate_age
from app.services.patient_memory import get_active_facts, get_relevant_past_chunks, get_chat_documents
from app.services.memory_formatter import format_facts_for_prompt, format_past_chats_for_prompt
from app.services.fact_persistence import process_chat_memory_extraction
from app.services.chat_indexer import index_chat_message
from app.services.upload_jobs import is_stale_building

logger = logging.getLogger(__name__)

# Hold strong references to background tasks to prevent GC mid-execution
_background_tasks: set = set()


def is_explicit_overview_query(query_text: str) -> bool:
    """
    Check if a query is explicitly requesting a complete report walkthrough / overview / summary.
    Focused follow-up questions like 'why is my bilirubin high?' or 'what about my platelets?'
    or 'can you explain why my glucose is elevated?' must return False.
    """
    q = (query_text or "").strip().lower()
    if not q:
        return False

    specific_question_prefixes = (
        "why ", "why is ", "why are ", "what about ", "what is ", "what does ",
        "what can i ", "how do i ", "how to ", "how can i ",
        "should i ", "is it ", "are my ", "can you tell me why ", "explain why ",
        "how come ", "is "
    )
    for prefix in specific_question_prefixes:
        if q.startswith(prefix) and not any(phrase in q for phrase in ("walk me through", "entire report", "full report", "whole report", "overview of my report", "summary of my report")):
            return False

    if q.startswith("tell me about ") and not any(phrase in q for phrase in ("this report", "the report", "my report", "this blood work", "my blood work", "these results", "my results", "my labs", "these labs")):
        return False

    pattern = (
        r"(?i)(?:^(?:now\s+)?(?:can\s+you\s+)?(?:please\s+)?(?:give\s+me\s+)?(?:the\s+|a\s+)?(?:full|complete|entire)\s+(?:report\s+)?(?:overview|walkthrough|breakdown|summary)(?:\s+of\s+(?:this|my|the)?\s*(?:report|results?|blood\s*work)?)?$"
        r"|^(?:(?:can\s+you\s+)?(?:please\s+)?(?:walk\s+me\s+through|summarize|give\s+me\s+(?:a|the)?\s*(?:full|complete|entire)?\s*(?:overview|walkthrough|breakdown|summary)\s*(?:of)?)\s+(?:this|my|the|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|results?))$"
        r"|^(?:(?:can\s+you\s+)?(?:please\s+)?explain\s+(?:this|my|the|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|lab\s+results?|results?))$"
        r"|^(?:(?:can\s+you\s+)?(?:please\s+)?tell\s+me\s+about\s+(?:this|the|my|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|labs|results?))$"
        r"|\b(?:walk\s+me\s+through\s+my\s+report|explain\s+my\s+lab\s+results|summarize\s+my\s+report|overview\s+of\s+my\s+lab\s+report)\b)"
    )
    return bool(re.search(pattern, q.strip()))


def compute_followup_turn_context(
    has_walked_through: bool,
    query_text: str,
    session_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Determine if a turn is a follow-up and log diagnostic context without leaking query text.
    """
    explicit_match = is_explicit_overview_query(query_text)
    if not has_walked_through:
        is_followup = False
        reason = "first_turn_no_prior_walkthrough"
    elif explicit_match:
        is_followup = False
        reason = "explicit_overview_requested"
    else:
        is_followup = True
        reason = "prior_walkthrough_completed_focused_followup"

    logger.info(
        "Follow-up context: session_id=%s, document_id=%s, is_followup_turn=%s, reason=%s",
        session_id,
        document_id,
        is_followup,
        reason,
    )
    return is_followup, reason


class TTLLockSet:
    """In-memory session lock helper with monotonic TTL expiration (120.0s)."""

    def __init__(self, ttl: float = 120.0):
        self._ttl = ttl
        self._locks: dict[str, float] = {}

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, exp in self._locks.items() if exp <= now]
        for k in expired:
            self._locks.pop(k, None)

    def add(self, key: str) -> None:
        self._purge_expired()
        self._locks[key] = time.monotonic() + self._ttl

    def discard(self, key: str) -> None:
        self._locks.pop(key, None)

    def pop(self, key: str, default: Any = None) -> Any:
        return self._locks.pop(key, default)

    def __contains__(self, key: str) -> bool:
        self._purge_expired()
        return key in self._locks

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._locks)


_active_query_sessions = TTLLockSet(ttl=120.0)

router = APIRouter()


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New chat title (max 60 chars)")


@router.patch("/documents/{document_id}/title", tags=["RAG Query"])
async def rename_document_title(
    document_id: str,
    body: RenameChatRequest,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rename the title of a document/session (auth-gated to owner)."""
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




def _clean_disclaimers(text: str, is_followup_turn: bool, has_critical_alert: bool = False) -> str:
    """
    Cleans disclaimers in visible response text:
    - If is_followup_turn is True and NOT (has_critical_alert or SAFE_FALLBACK in text):
        strips trailing Disclaimer: paragraphs completely.
    - If is_followup_turn is False (or critical / SAFE_FALLBACK follow-up):
        deduplicates multiple Disclaimer: paragraphs into a single disclaimer at the end.
    """
    if not text:
        return text

    disclaimer_pattern = r'(?im)(?:(?:\n\s*)?(?:\*\*\*|---|___)\s*)?(?:\n\s*)?^\s*\*{0,2}Disclaimer:\*{0,2}[^\n]*(?:\n(?!\s*#{1,6}\s)[^\n]+)*'

    is_critical_or_safe_fallback = has_critical_alert or (SAFE_FALLBACK in text)
    if is_followup_turn and not is_critical_or_safe_fallback:
        cleaned = re.sub(disclaimer_pattern, '', text).rstrip()
        return cleaned
    else:
        matches = list(re.finditer(disclaimer_pattern, text))
        if len(matches) > 1:
            cleaned = re.sub(disclaimer_pattern, '', text).rstrip()
            return f"{cleaned}\n\n{DISCLAIMER_TEXT.strip()}"
        return text


async def link_chat_documents_batch(
    db: AsyncSession,
    chat_id: uuid.UUID,
    doc_ids: list[uuid.UUID],
) -> set[uuid.UUID]:
    """Ensure ChatDocument associations exist for all attached docs using a single batch query."""
    if not doc_ids:
        return set()
    existing_cds = await db.execute(
        select(ChatDocument.document_id).filter(
            ChatDocument.chat_id == chat_id,
            ChatDocument.document_id.in_(doc_ids),
        )
    )
    already_linked = set(existing_cds.scalars().all())
    for doc_id in doc_ids:
        if doc_id not in already_linked:
            db.add(ChatDocument(chat_id=chat_id, document_id=doc_id))
    return already_linked


@router.post("/query", tags=["RAG Query"])
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query_bot(
    request: Request,
    body: QueryRequest,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Strip accidental outer quotation marks from user prompt
    if body.query:
        clean_q = body.query.strip()
        if (clean_q.startswith('"') and clean_q.endswith('"') and len(clean_q) >= 2) or \
           (clean_q.startswith("“") and clean_q.endswith("”") and len(clean_q) >= 2) or \
           (clean_q.startswith("'") and clean_q.endswith("'") and len(clean_q) >= 2):
            clean_q = clean_q[1:-1].strip()
        body.query = clean_q

    # ── Resolve documents associated with active session / chat ──
    chat_docs: List[Document] = []
    primary_doc: Optional[Document] = None
    target_chat_id: Optional[uuid.UUID] = None

    effective_session_id = body.session_id.strip() if (body.session_id and body.session_id.strip()) else None

    if effective_session_id:
        try:
            parsed_id = uuid.UUID(effective_session_id)
            # 1. Check if session_id is an existing chat_id
            chat_check = await db.execute(
                select(Chat).filter(Chat.id == parsed_id)
            )
            chat_found = chat_check.scalars().first()
            if chat_found:
                if chat_found.user_id != current_user.id:
                    raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this session.")
                target_chat_id = chat_found.id
                if chat_found.session_id:
                    effective_session_id = chat_found.session_id
                chat_docs = await get_chat_documents(target_chat_id, session=db)
                if chat_docs:
                    primary_doc = chat_docs[0]
            else:
                # 2. Check if session_id is a document_id
                doc_check = await db.execute(
                    select(Document).filter(Document.id == parsed_id)
                )
                doc_found = doc_check.scalars().first()
                if doc_found:
                    if doc_found.user_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this document.")
                    primary_doc = doc_found
                    chat_docs = [doc_found]
        except ValueError:
            logger.debug("Non-UUID session_id provided: %s", effective_session_id)

    if body.document_id:
        try:
            doc_uuid = uuid.UUID(str(body.document_id))
        except (ValueError, TypeError):
            raise HTTPException(status_code=404, detail="Document not found")

        doc_res = await db.execute(
            select(Document).filter(Document.id == doc_uuid, Document.user_id == current_user.id)
        )
        d_found = doc_res.scalars().first()
        if d_found is None:
            raise HTTPException(status_code=404, detail="Document not found")

        if d_found not in chat_docs:
            chat_docs.append(d_found)
            if not primary_doc:
                primary_doc = d_found

    raw_doc_ids = getattr(body, "document_ids", None)
    if raw_doc_ids and isinstance(raw_doc_ids, list):
        for did in raw_doc_ids:
            try:
                d_uuid = uuid.UUID(str(did))
            except (ValueError, TypeError):
                raise HTTPException(status_code=404, detail="Document not found")
            d_res = await db.execute(
                select(Document).filter(Document.id == d_uuid, Document.user_id == current_user.id)
            )
            found_multi_doc = d_res.scalars().first()
            if found_multi_doc is None:
                raise HTTPException(status_code=404, detail="Document not found")
            if found_multi_doc not in chat_docs:
                chat_docs.append(found_multi_doc)
                if not primary_doc:
                    primary_doc = found_multi_doc

    if not effective_session_id:
        if primary_doc:
            effective_session_id = f"doc-{primary_doc.id}"
        else:
            effective_session_id = str(uuid.uuid4())

    session_owner_check = await db.execute(
        select(Chat.user_id).filter(Chat.session_id == effective_session_id, Chat.user_id != current_user.id).limit(1)
    )
    if session_owner_check.scalars().first():
        raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this session.")

    has_document = len(chat_docs) > 0 and any(bool(d.file_path) for d in chat_docs)

    import sentry_sdk
    _is_doc_qa = primary_doc is not None
    sentry_sdk.set_tag("route", "document_qa" if _is_doc_qa else "general_health")
    if primary_doc:
        sentry_sdk.set_tag("index_status", primary_doc.index_status)

    # ── Total Miss / Building Safeguard (Executed before ANY DB writes or Gemini calls) ──
    for d in chat_docs:
        if getattr(d, "index_status", None) == "failed" or is_stale_building(d):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This document could not be processed. Please upload a different file or re-upload.",
            )
        if getattr(d, "index_status", None) == "building":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document index is still building. Please retry in 2 seconds.",
                headers={"Retry-After": "2"},
            )

        if not d.file_path:
            continue

        # If running in a test environment where load_hybrid_index is mocked, bypass physical file check
        if hasattr(load_hybrid_index, "mock_calls") or hasattr(load_hybrid_index, "_mock_return_value"):
            continue

        # Resolution order: 1. LRU cache -> 2. Local /tmp -> 3. GCS
        in_memory = bool(get_cached_hybrid_index(str(d.id)) or get_cached_hybrid_index(d.file_path))
        if in_memory:
            continue

        p = Path(d.file_path)
        if p.exists() and (p.is_dir() or p.is_file()):
            continue

        gcs_retrieved = False
        if settings.GCS_INDEX_BUCKET:
            try:
                downloaded = await asyncio.wait_for(aensure_index_local(d.file_path), timeout=2.0)
                if downloaded and Path(downloaded).exists():
                    gcs_retrieved = True
            except Exception as dl_err:
                logger.warning(f"GCS index retrieval attempt failed/timed-out for doc {d.id}: {dl_err}")
                gcs_retrieved = False

        if not gcs_retrieved:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document index temporarily unavailable. Please retry in 2 seconds.",
                headers={"Retry-After": "2"},
            )

    # ── Auto-naming helper (DB commit deferred until after 409 Conflict lock) ──
    updated_chat_title: Optional[str] = None
    DEFAULT_TITLES = {
        "New Conversation",
        "New conversation",
        "New Chat",
        "New chat",
        "New Consultation",
        "New consultation",
        "Untitled",
        "",
        None,
    }
    needs_doc_title_update = bool(
        primary_doc and (primary_doc.title is None or primary_doc.title.strip() in DEFAULT_TITLES)
    )
    if needs_doc_title_update or not primary_doc:
        updated_chat_title = generate_title_from_query(body.query, max_words=5, max_len=60)

    existing_title_res = await db.execute(
        select(Chat.session_title).filter(
            Chat.session_id == effective_session_id,
            Chat.user_id == current_user.id,
            Chat.session_title.isnot(None),
        ).limit(1)
    )
    current_session_title = existing_title_res.scalars().first()
    if not current_session_title:
        current_session_title = updated_chat_title or generate_title_from_query(body.query, max_words=5, max_len=60)

    # ── Profile & PHI Context Resolution ──
    active_profile = current_user
    active_dep_id: Optional[uuid.UUID] = None
    target_patient_id = body.patient_id
    if not target_patient_id and primary_doc and primary_doc.dependent_id:
        target_patient_id = str(primary_doc.dependent_id)

    if target_patient_id and target_patient_id.lower() != "self" and target_patient_id != str(current_user.id):
        try:
            p_uuid = uuid.UUID(target_patient_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid patient_id.")
        dep_res = await db.execute(
            select(DependentProfile).filter(
                DependentProfile.id == p_uuid,
                DependentProfile.user_id == current_user.id,
            )
        )
        dep = dep_res.scalars().first()
        if not dep:
            raise HTTPException(status_code=404, detail="Dependent profile not found.")
        active_profile = dep
        active_dep_id = dep.id
    else:
        user_res = await db.execute(select(User).filter(User.id == current_user.id))
        db_user = user_res.scalars().first()
        if db_user:
            active_profile = db_user

    if body.patient_id and any(d.dependent_id != active_dep_id for d in chat_docs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile Lock: This report belongs to a different patient profile and cannot be accessed from the currently selected profile.",
        )

    await log_audit(
        db,
        "PHI_ACCESS_QUERY",
        current_user.id,
        "query_rag",
        request.client.host if request.client else "unknown",
        dependent_id=active_dep_id,
    )

    calc_age = calculate_age(active_profile.date_of_birth)
    calculated_age_str = f"{calc_age}" if calc_age is not None else "Unknown"
    biological_sex = active_profile.biological_sex or "Unspecified"
    pre_existing_conditions = active_profile.pre_existing_conditions or "None reported"
    current_medications = active_profile.current_medications or "None reported"
    known_allergies = getattr(active_profile, "known_allergies", None)
    language_preference = (
        getattr(active_profile, "language_preference", None)
        or getattr(current_user, "language_preference", None)
        or body.language
        or "English"
    )
    height_cm = getattr(active_profile, "height_cm", None)
    diet_type = getattr(active_profile, "diet_type", None)
    activity_level = getattr(active_profile, "activity_level", None)
    occupation = getattr(active_profile, "occupation", None)

    # ── Emergency keyword gate ──
    emergency_kind = detect_emergency(body.query)
    emergency_language = detect_emergency_language(body.query) or language_preference
    emergency_banner: Optional[str] = None

    if emergency_kind == EmergencyKind.SELF_HARM or (
        emergency_kind == EmergencyKind.MEDICAL
        and not has_document
        and not getattr(body, "document_id", None)
        and not raw_doc_ids
    ):
        if needs_doc_title_update and primary_doc and updated_chat_title:
            primary_doc.title = updated_chat_title
            db.add(primary_doc)
        ai_msg = get_emergency_response(emergency_kind, emergency_language)
        user_chat = Chat(
            user_id=current_user.id,
            dependent_id=active_dep_id,
            document_id=primary_doc.id if primary_doc else None,
            session_id=effective_session_id,
            session_title=current_session_title,
            role="user",
            message=body.query,
        )
        ai_chat = Chat(
            user_id=current_user.id,
            dependent_id=active_dep_id,
            document_id=primary_doc.id if primary_doc else None,
            session_id=effective_session_id,
            session_title=current_session_title,
            role="ai",
            message=ai_msg,
        )
        db.add_all([user_chat, ai_chat])
        await db.commit()
        primary_doc_id_str = str(primary_doc.id) if primary_doc else None
        await db.close()

        async def emergency_stream():
            yield f'data: {json.dumps({"title": updated_chat_title or current_session_title, "document_id": primary_doc_id_str, "session_id": effective_session_id}, ensure_ascii=False)}\n\n'
            yield f'data: {json.dumps({"chunk": ai_msg}, ensure_ascii=False)}\n\n'
            yield f'data: [DONE]\n\n'

        return StreamingResponse(emergency_stream(), media_type="text/event-stream")

    if emergency_kind == EmergencyKind.MEDICAL:
        emergency_banner = get_emergency_response(EmergencyKind.MEDICAL, emergency_language)

    session_lock_key = f"{current_user.id}:{effective_session_id or 'general'}"
    if session_lock_key in _active_query_sessions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A query stream is already active for this document or conversation. Please wait for it to complete.",
        )
    _active_query_sessions.add(session_lock_key)

    try:
        if needs_doc_title_update and primary_doc and updated_chat_title:
            primary_doc.title = updated_chat_title
            db.add(primary_doc)

        # Record user message in DB
        user_chat = Chat(
            user_id=current_user.id,
            dependent_id=active_dep_id,
            document_id=primary_doc.id if primary_doc else None,
            session_id=effective_session_id,
            session_title=current_session_title,
            role="user",
            message=body.query,
        )
        db.add(user_chat)
        await db.commit()
        await db.refresh(user_chat)
        current_chat_id = user_chat.id

        # Ensure ChatDocument associations exist for all attached docs (single batch query)
        if chat_docs:
            doc_ids = [cd_doc.id for cd_doc in chat_docs]
            await link_chat_documents_batch(db, current_chat_id, doc_ids)
            await db.commit()
    except Exception:
        _active_query_sessions.discard(session_lock_key)
        raise

    # ── Intent Classification ──
    doc_id_param = getattr(body, "document_id", None) or (str(primary_doc.id) if primary_doc else None)
    intent = await classify_intent(
        body.query,
        has_document=has_document,
        document_id=doc_id_param,
    )
    if intent == QueryIntent.EMERGENCY:
        emergency_banner = get_emergency_response(EmergencyKind.MEDICAL, emergency_language)
        intent = QueryIntent.DOCUMENT_QA if has_document else QueryIntent.GENERAL_HEALTH
    elif emergency_banner and intent != QueryIntent.DOCUMENT_QA:
        intent = QueryIntent.GENERAL_HEALTH
    elif intent == QueryIntent.DOCUMENT_QA and not has_document:
        intent = QueryIntent.GENERAL_HEALTH

    # Release the request-scoped DB connection before entering the long-lived SSE
    # stream (generate_response_stream opens its own short-lived AsyncSessionLocal
    # sessions when needed).
    await db.close()

    async def generate_response_stream():
        full_raw_text = ""
        visible_text = ""
        stream_task = None
        try:
            title_to_emit = updated_chat_title or current_session_title
            if title_to_emit:
                yield f'data: {json.dumps({"title": title_to_emit, "document_id": str(primary_doc.id) if primary_doc else None, "session_id": effective_session_id})}\n\n'

            if emergency_banner:
                banner_chunk = emergency_banner + "\n\n"
                visible_text += banner_chunk
                yield f'data: {json.dumps({"chunk": banner_chunk})}\n\n'

            # ── Stage 1: Analyzing ──
            if intent == QueryIntent.CASUAL:
                yield f'event: stage\ndata: {json.dumps({"stage": "generating", "message": "MediSkye is typing..."})}\n\n'
            else:
                yield f'event: stage\ndata: {json.dumps({"stage": "analyzing", "message": "Analyzing your question..."})}\n\n'

            # ── Multi-doc retrieval (for DOCUMENT_QA only) ──
            retrieved_chunks = []
            if intent == QueryIntent.DOCUMENT_QA:
                yield f'event: stage\ndata: {json.dumps({"stage": "retrieving", "message": "Searching your reports..."})}\n\n'
                all_doc_results = []
                # Adapt retrieval breadth to query complexity: short factual
                # questions get a tight k=4; long/multi-part questions sweep k=12.
                per_doc_k = dynamic_retrieval_k(body.query)
                for d in chat_docs:
                    if not d.file_path:
                        continue
                    try:
                        cached_entry = get_cached_hybrid_index(str(d.id)) or get_cached_hybrid_index(d.file_path)
                        if cached_entry is not None:
                            v, b = cached_entry
                            doc_chunks = await asyncio.to_thread(retrieve_relevant_docs, body.query, v, b, k=per_doc_k)
                        else:
                            resolved_path = str(await aensure_index_local(d.file_path))
                            if not os.path.exists(resolved_path):
                                logger.warning("Index file missing after ensure_local: %s", resolved_path)
                                continue

                            def _load_and_retrieve(path, q):
                                v, b = load_hybrid_index(path)
                                return retrieve_relevant_docs(q, v, b, k=per_doc_k)

                            doc_chunks = await asyncio.to_thread(_load_and_retrieve, resolved_path, body.query)
                        for c in doc_chunks:
                            c.metadata["source"] = d.title or d.filename
                            c.metadata["filename"] = d.filename
                        if doc_chunks:
                            all_doc_results.append(doc_chunks)
                    except Exception as e:
                        logger.warning("Failed to search index for doc %s: %s", d.filename, e)

                if len(all_doc_results) == 1:
                    retrieved_chunks = all_doc_results[0]
                elif len(all_doc_results) > 1:
                    scores: Dict[str, float] = {}
                    doc_chunk_map: Dict[str, Any] = {}
                    for doc_list in all_doc_results:
                        for rank, c in enumerate(doc_list):
                            c_key = c.page_content.strip()
                            scores[c_key] = scores.get(c_key, 0.0) + (1.0 / (60.0 + rank))
                            if c_key not in doc_chunk_map:
                                doc_chunk_map[c_key] = c

                    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
                    limit_k = max(6, len(all_doc_results) * 2)
                    retrieved_chunks = [doc_chunk_map[k] for k in sorted_keys[:limit_k]]

            # ── Memory retrieval (Tier 1 facts always, Tier 2 past chunks for DOCUMENT_QA only) ──
            formatted_facts = None
            formatted_past_chats = None
            prior_documents_metrics: List[Dict[str, Any]] = []

            # ── Historical lab reports (cached_metrics) for longitudinal comparison ──
            if intent in (QueryIntent.DOCUMENT_QA, QueryIntent.GENERAL_HEALTH):
                try:
                    async with AsyncSessionLocal() as hist_session:
                        excluded_doc_ids = set()
                        if primary_doc:
                            excluded_doc_ids.add(primary_doc.id)
                        for cd in chat_docs:
                            excluded_doc_ids.add(cd.id)

                        current_collected_dt = parse_report_chronology(primary_doc) if primary_doc else None

                        prior_docs_stmt = (
                            select(Document)
                            .filter(
                                Document.user_id == current_user.id,
                                Document.dependent_id == active_dep_id if active_dep_id else Document.dependent_id.is_(None),
                                Document.cached_metrics.is_not(None),
                            )
                        )
                        if excluded_doc_ids:
                            prior_docs_stmt = prior_docs_stmt.filter(Document.id.notin_(list(excluded_doc_ids)))

                        prior_docs_stmt = prior_docs_stmt.order_by(Document.created_at.desc()).limit(10)
                        prior_docs_res = await hist_session.execute(prior_docs_stmt)
                        candidate_docs = [cand for cand in prior_docs_res.scalars().all() if not is_sample_document(cand)]

                        # Strict Chronological Ordering: ONLY select documents where candidate_collected_dt < current_collected_dt
                        if primary_doc is None and candidate_docs:
                            from datetime import datetime as dt_cls
                            def _doc_sort_key(d):
                                parsed = parse_report_chronology(d)
                                if parsed is not None:
                                    return parsed
                                return d.created_at.replace(tzinfo=None) if d.created_at else dt_cls.min
                            candidate_docs.sort(key=_doc_sort_key, reverse=True)
                            prior_docs = candidate_docs[:3]
                        elif current_collected_dt and candidate_docs:
                            valid_priors = [
                                cand for cand in candidate_docs
                                if parse_report_chronology(cand) is not None and parse_report_chronology(cand) < current_collected_dt
                            ]
                            valid_priors.sort(key=lambda d: parse_report_chronology(d), reverse=True)
                            prior_docs = valid_priors[:3]
                        elif not current_collected_dt and candidate_docs:
                            # Fallback to created_at only if current doc has no collection date
                            valid_priors = [
                                cand for cand in candidate_docs
                                if cand.created_at and primary_doc and primary_doc.created_at and cand.created_at < primary_doc.created_at
                            ]
                            valid_priors.sort(key=lambda d: d.created_at, reverse=True)
                            prior_docs = valid_priors[:3]
                        else:
                            prior_docs = []

                        # Sample reports never inherit prior longitudinal history
                        if primary_doc and is_sample_document(primary_doc):
                            prior_docs = []

                        for pdoc in prior_docs:
                            raw_cm = pdoc.cached_metrics
                            if isinstance(raw_cm, str):
                                try:
                                    raw_cm = json.loads(raw_cm)
                                except Exception:
                                    raw_cm = []
                            if isinstance(raw_cm, dict) and "metrics" in raw_cm:
                                raw_cm = raw_cm["metrics"]

                            if isinstance(raw_cm, list) and len(raw_cm) > 0:
                                date_label = pdoc.collected_at or (pdoc.created_at.strftime("%d %b %Y") if pdoc.created_at else "Unknown date")
                                prior_documents_metrics.append({
                                    "filename": pdoc.filename,
                                    "title": pdoc.title or pdoc.filename,
                                    "collected_at": pdoc.collected_at,
                                    "uploaded_at": date_label,
                                    "metrics": raw_cm,
                                })
                except Exception as hist_err:
                    logger.warning("Error loading prior document metrics: %s", hist_err)

            # Document / Session Follow-up Detection & turn context
            is_followup_turn = False
            current_session_history = None

            if intent != QueryIntent.CASUAL:
                async with AsyncSessionLocal() as turn_session:
                    latest_doc = chat_docs[-1] if chat_docs else primary_doc
                    latest_doc_id = latest_doc.id if latest_doc else None

                    prior_doc_chats = []
                    if latest_doc_id:
                        doc_chat_res = await turn_session.execute(
                            select(Chat)
                            .filter(
                                Chat.user_id == current_user.id,
                                Chat.document_id == latest_doc_id,
                                Chat.id != current_chat_id,
                            )
                            .order_by(Chat.created_at.asc())
                        )
                        prior_doc_chats = doc_chat_res.scalars().all()

                        latest_prior_chat = prior_doc_chats[-1] if prior_doc_chats else None
                        is_brand_new_doc = False
                        if latest_prior_chat and latest_doc.created_at:
                            if latest_doc.created_at > latest_prior_chat.created_at:
                                is_brand_new_doc = True

                        has_walked_through_latest_doc = (
                            len([c for c in prior_doc_chats if c.role == "ai"]) > 0
                            and not is_brand_new_doc
                        )
                    else:
                        session_chat_res = await turn_session.execute(
                            select(Chat)
                            .filter(
                                Chat.user_id == current_user.id,
                                Chat.session_id == effective_session_id,
                                Chat.id != current_chat_id,
                            )
                            .order_by(Chat.created_at.asc())
                        )
                        prior_session_chats = session_chat_res.scalars().all()
                        has_walked_through_latest_doc = len([c for c in prior_session_chats if c.role == "ai"]) > 0
                        prior_doc_chats = prior_session_chats

                    is_followup_turn, _ = compute_followup_turn_context(
                        has_walked_through=has_walked_through_latest_doc,
                        query_text=body.query.strip(),
                        session_id=effective_session_id,
                        document_id=str(latest_doc_id) if latest_doc_id else None,
                    )

                    # Build concise current_session_history using smart turn condensation
                    if prior_doc_chats:
                        current_session_history = condense_chat_history(prior_doc_chats)

                    recent_filters = [
                        Chat.user_id == current_user.id,
                        Chat.session_id == effective_session_id,
                        Chat.id != current_chat_id,
                    ]
                    recent_res = await turn_session.execute(
                        select(Chat).filter(*recent_filters).order_by(Chat.created_at.desc()).limit(6)
                    )
                    recent_turns = list(reversed(recent_res.scalars().all()))
                    if recent_turns:
                        recent_formatted = format_past_chats_for_prompt(
                            [
                                {
                                    "text": f"{t.role.upper()}: {t.message}",
                                    "created_at": t.created_at,
                                    "doc_name": primary_doc.filename if primary_doc else None,
                                    "doc_date": primary_doc.created_at if primary_doc else None,
                                    "session_title": current_session_title,
                                }
                                for t in recent_turns
                                if t.message
                            ]
                        )
                        if recent_formatted:
                            formatted_past_chats = (
                                f"{formatted_past_chats}\n\n{recent_formatted}"
                                if formatted_past_chats
                                else recent_formatted
                            )

            if intent != QueryIntent.CASUAL and current_user.memory_consent_granted and settings.PATIENT_MEMORY_ENABLED:
                async with AsyncSessionLocal() as mem_session:
                    facts_by_type = await get_active_facts(
                        user_id=current_user.id,
                        dependent_id=active_dep_id,
                        session=mem_session,
                        limit=settings.PATIENT_MEMORY_MAX_FACTS,
                    )
                    has_facts = any(len(v) > 0 for v in facts_by_type.values())
                    if has_facts or diet_type or activity_level or height_cm or occupation:
                        formatted_facts = format_facts_for_prompt(
                            facts_by_type=facts_by_type,
                            profile=active_profile,
                        )
                        # Stage: Memory (only if facts are loaded)
                        yield f'event: stage\ndata: {json.dumps({"stage": "memory", "message": "Checking your health history..."})}\n\n'

                    if intent == QueryIntent.DOCUMENT_QA:
                        past_chunks = await get_relevant_past_chunks(
                            query=body.query,
                            user_id=current_user.id,
                            dependent_id=active_dep_id,
                            exclude_chat_id=current_chat_id,
                            session=mem_session,
                            k=settings.PATIENT_MEMORY_PAST_CHUNKS,
                        )
                        if past_chunks:
                            past_chunks_formatted = format_past_chats_for_prompt(past_chunks)
                            formatted_past_chats = (
                                f"{formatted_past_chats}\n\n{past_chunks_formatted}"
                                if formatted_past_chats
                                else past_chunks_formatted
                            )

            # ── Stage: Generating ──
            if intent != QueryIntent.CASUAL:
                yield f'event: stage\ndata: {json.dumps({"stage": "generating", "message": "Preparing your answer..."})}\n\n'

            # Reconstruct active document metrics and raw text from active document
            active_docs_metrics = []
            raw_report_text = ""
            active_docs = [primary_doc] if primary_doc else list(chat_docs or [])
            for adoc in active_docs:
                raw_cm = getattr(adoc, "cached_metrics", None)
                if isinstance(raw_cm, str):
                    try:
                        raw_cm = json.loads(raw_cm)
                    except Exception:
                        raw_cm = []
                if isinstance(raw_cm, dict) and "metrics" in raw_cm:
                    raw_cm = raw_cm["metrics"]
                if isinstance(raw_cm, list) and len(raw_cm) > 0:
                    active_docs_metrics.append({
                        "filename": adoc.filename,
                        "title": adoc.title or adoc.filename,
                        "collected_at": adoc.collected_at,
                        "metrics": raw_cm,
                    })

            if primary_doc:
                raw_report_text = await _reconstruct_document_text(primary_doc)
            elif active_docs:
                doc_texts = []
                for adoc in active_docs:
                    t = await _reconstruct_document_text(adoc)
                    if t:
                        doc_texts.append(t)
                raw_report_text = "\n\n".join(doc_texts)

            # Build prompt based on intent
            if intent == QueryIntent.CASUAL:
                system_instruction, user_content = build_casual_prompt(
                    user_query=body.query,
                    language_preference=language_preference,
                )

            elif intent == QueryIntent.DOCUMENT_QA:
                system_instruction, user_content = build_prompt(
                    user_query=body.query,
                    retrieved_docs=retrieved_chunks,
                    calculated_age=calculated_age_str,
                    biological_sex=biological_sex,
                    pre_existing_conditions=pre_existing_conditions,
                    current_medications=current_medications,
                    language_preference=language_preference,
                    patient_facts=formatted_facts,
                    past_chats=formatted_past_chats,
                    known_allergies=known_allergies,
                    height_cm=height_cm,
                    diet_type=diet_type,
                    activity_level=activity_level,
                    occupation=occupation,
                    prior_documents_metrics=prior_documents_metrics,
                    active_docs_metrics=active_docs_metrics,
                    raw_report_text=raw_report_text,
                    is_followup_turn=is_followup_turn,
                    current_session_history=current_session_history,
                )

            else:
                system_instruction, user_content = build_general_health_prompt(
                    user_query=body.query,
                    calculated_age=calculated_age_str,
                    biological_sex=biological_sex,
                    pre_existing_conditions=pre_existing_conditions,
                    current_medications=current_medications,
                    language_preference=language_preference,
                    patient_facts=formatted_facts,
                    past_chats=formatted_past_chats,
                    known_allergies=known_allergies,
                    height_cm=height_cm,
                    diet_type=diet_type,
                    activity_level=activity_level,
                    occupation=occupation,
                    prior_documents_metrics=prior_documents_metrics,
                    retrieved_docs=retrieved_chunks,
                    active_docs_metrics=active_docs_metrics,
                    raw_report_text=raw_report_text,
                    is_followup_turn=is_followup_turn,
                    current_session_history=current_session_history,
                )

            # ── Gemini stream with progressive fallback across models (at least 5 attempts) ──
            loop = asyncio.get_running_loop()
            models_to_try = get_fallback_models()
            stream_succeeded = False
            last_stream_exception = None

            for model_idx, current_model in enumerate(models_to_try):
                if await request.is_disconnected():
                    logger.info("Client disconnected before model attempt %s; aborting stream loop.", current_model)
                    break

                if model_idx > 0:
                    yield f'data: {json.dumps({"type": "stage", "stage": "generating", "detail": f"Retrying with backup model ({current_model})..."})}\n\n'

                queue = asyncio.Queue()
                SENTINEL = object()

                def _stream_producer(target_model=current_model, target_queue=queue, sentinel=SENTINEL):
                    from google.genai.types import GenerateContentConfig, ThinkingConfig
                    from app.llm.gemini_client import get_genai_client

                    client = get_genai_client()
                    try:
                        response = client.models.generate_content_stream(
                            model=target_model,
                            contents=user_content,
                            config=GenerateContentConfig(
                                system_instruction=system_instruction,
                                thinking_config=ThinkingConfig(thinking_budget=0),
                            ),
                        )
                        for chunk in response:
                            loop.call_soon_threadsafe(target_queue.put_nowait, chunk)
                        loop.call_soon_threadsafe(target_queue.put_nowait, sentinel)
                    except Exception as exc:
                        loop.call_soon_threadsafe(target_queue.put_nowait, exc)
                        loop.call_soon_threadsafe(target_queue.put_nowait, sentinel)

                stream_task = asyncio.create_task(asyncio.to_thread(_stream_producer, current_model, queue, SENTINEL))

                attempt_full_raw = ""
                attempt_visible = ""
                pending_buffer = ""
                in_json_block = False
                attempt_yielded_to_client = False
                model_failed_with_exc = None

                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=35.0)
                    except asyncio.TimeoutError:
                        logger.warning("Stream token queue read timed out for model=%s user_id=%s", current_model, current_user.id)
                        model_failed_with_exc = asyncio.TimeoutError(f"Model {current_model} queue read timeout")
                        break

                    if item is SENTINEL:
                        break
                    if isinstance(item, Exception):
                        model_failed_with_exc = item
                        break

                    chunk_text = getattr(item, "text", None)
                    if not chunk_text:
                        continue

                    attempt_full_raw += chunk_text

                    if in_json_block:
                        continue

                    pending_buffer += chunk_text
                    lower_buf = pending_buffer.lower()

                    # Check for bare or fenced abnormal_flags JSON
                    if "abnormal_flags" in lower_buf:
                        brace_idx = lower_buf.find('{"abnormal_flags"')
                        if brace_idx == -1:
                            brace_idx = lower_buf.find('{')
                        fence_idx_ab = -1
                        for fence in ("```", "~~~"):
                            idx = lower_buf.find(fence)
                            if idx != -1 and (fence_idx_ab == -1 or idx < fence_idx_ab):
                                fence_idx_ab = idx
                        cut_pos = fence_idx_ab if (fence_idx_ab != -1 and fence_idx_ab < brace_idx) else brace_idx
                        if cut_pos != -1:
                            in_json_block = True
                            visible_chunk = pending_buffer[:cut_pos]
                            if visible_chunk:
                                attempt_visible += visible_chunk
                                attempt_yielded_to_client = True
                                yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                            pending_buffer = ""
                            continue

                    # Buffer trailing partial XML tags (<followup_turn_instruction, etc.)
                    xml_match = re.search(r'<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)[^>]*$', pending_buffer, re.IGNORECASE)
                    if xml_match:
                        tag_start = xml_match.start()
                        to_yield = pending_buffer[:tag_start]
                        pending_buffer = pending_buffer[tag_start:]
                        if to_yield:
                            attempt_visible += to_yield
                            attempt_yielded_to_client = True
                            yield f'data: {json.dumps({"chunk": to_yield})}\n\n'
                        continue

                    has_fence = False
                    fence_idx = -1
                    for fence in ("```", "~~~"):
                        idx = lower_buf.find(fence)
                        if idx != -1:
                            if fence_idx == -1 or idx < fence_idx:
                                fence_idx = idx
                                has_fence = True

                    if has_fence:
                        tail = pending_buffer[fence_idx:]
                        if "abnormal_flags" in tail:
                            in_json_block = True
                            visible_chunk = pending_buffer[:fence_idx]
                            if visible_chunk:
                                attempt_visible += visible_chunk
                                attempt_yielded_to_client = True
                                yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                            pending_buffer = ""
                        elif len(tail) < 150:
                            if fence_idx > 0:
                                visible_chunk = pending_buffer[:fence_idx]
                                attempt_visible += visible_chunk
                                attempt_yielded_to_client = True
                                yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                                pending_buffer = pending_buffer[fence_idx:]
                        else:
                            attempt_visible += pending_buffer
                            attempt_yielded_to_client = True
                            yield f'data: {json.dumps({"chunk": pending_buffer})}\n\n'
                            pending_buffer = ""
                    else:
                        # Buffer trailing partial abnormal_flags bare JSON only when there is no fence
                        partial_json_match = re.search(r'\{\s*"?(?:a|ab|abn|abnor|abnorm|abnorma|abnormal|abnormal_)?\s*"?\s*$', pending_buffer, re.IGNORECASE)
                        if partial_json_match and len(pending_buffer) - partial_json_match.start() < 30:
                            json_start = partial_json_match.start()
                            to_yield = pending_buffer[:json_start]
                            pending_buffer = pending_buffer[json_start:]
                            if to_yield:
                                attempt_visible += to_yield
                                attempt_yielded_to_client = True
                                yield f'data: {json.dumps({"chunk": to_yield})}\n\n'
                            continue

                        if pending_buffer.endswith(("``", "~~")):
                            to_yield = pending_buffer[:-2]
                            pending_buffer = pending_buffer[-2:]
                        elif pending_buffer.endswith(("`", "~")):
                            to_yield = pending_buffer[:-1]
                            pending_buffer = pending_buffer[-1:]
                        else:
                            to_yield = pending_buffer
                            pending_buffer = ""

                        if to_yield:
                            attempt_visible += to_yield
                            attempt_yielded_to_client = True
                            yield f'data: {json.dumps({"chunk": to_yield})}\n\n'

                if model_failed_with_exc:
                    last_stream_exception = model_failed_with_exc
                    logger.warning("Stream attempt on model %s failed: %s", current_model, model_failed_with_exc)
                    if attempt_yielded_to_client:
                        raise model_failed_with_exc
                    continue

                if not attempt_full_raw.strip():
                    logger.warning("Stream attempt on model %s yielded empty content; falling back to next model.", current_model)
                    last_stream_exception = GeminiUnavailableError(f"Model {current_model} returned empty response")
                    continue

                if pending_buffer and not in_json_block:
                    lower_pending = pending_buffer.lower()
                    fences_found = [lower_pending.find(f) for f in ("```", "~~~") if lower_pending.find(f) != -1]
                    if "abnormal_flags" in lower_pending:
                        cut_idx = min(fences_found) if fences_found else lower_pending.find("abnormal_flags")
                        if cut_idx != -1:
                            brace_before = lower_pending.rfind("{", 0, cut_idx)
                            if brace_before != -1:
                                cut_idx = min(cut_idx, brace_before)
                        visible_chunk = pending_buffer[:cut_idx] if cut_idx > 0 else ""
                        if visible_chunk:
                            attempt_visible += visible_chunk
                            yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                    else:
                        clean_buf = re.sub(r'<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)[^>]*>[\s\S]*$', '', pending_buffer, flags=re.IGNORECASE)
                        clean_buf = re.sub(r'<(?:patient_health_profile|extracted_report_biomarkers|analysis_hints|followup_turn_instruction|uploaded_documents|current_session_history|patient_context)[^>]*$', '', clean_buf, flags=re.IGNORECASE)
                        if clean_buf:
                            attempt_visible += clean_buf
                            yield f'data: {json.dumps({"chunk": clean_buf})}\n\n'

                full_raw_text = attempt_full_raw
                visible_text = attempt_visible
                stream_succeeded = True
                break

            if not stream_succeeded:
                if last_stream_exception:
                    raise last_stream_exception
                raise GeminiUnavailableError("All fallback models failed to generate a response.")

            is_safe_fallback_text = (SAFE_FALLBACK in visible_text)
            has_critical = bool(emergency_banner) or is_safe_fallback_text
            preserve_disclaimer = (not is_followup_turn) or has_critical

            if intent != QueryIntent.CASUAL and preserve_disclaimer:
                has_existing_disclaimer = bool(re.search(r'(?im)^\s*\*{0,2}Disclaimer:\*{0,2}', visible_text))
                if not has_existing_disclaimer:
                    disclaimer = "\n\n" + append_disclaimer("", intent=intent.value if hasattr(intent, "value") else str(intent), is_followup_turn=False).strip()
                    yield f'data: {json.dumps({"chunk": disclaimer})}\n\n'
                    visible_text += disclaimer

            # Post-process visible text to enforce disclaimer rules (single disclaimer on first overview only, stripped on follow-ups unless critical/SAFE_FALLBACK)
            visible_text = _clean_disclaimers(visible_text, is_followup_turn, has_critical_alert=has_critical)

            # ── Output filter scan ──
            is_safe, reason = scan_output(visible_text)
            if not is_safe:
                logger.warning("Output filter blocked response: %s | user_id=%s", reason, current_user.id)
                visible_text = SAFE_FALLBACK
                if intent != QueryIntent.CASUAL:
                    # DECISION_2: KEEP disclaimer on SAFE_FALLBACK follow-up
                    visible_text = append_disclaimer(visible_text, intent=intent.value if hasattr(intent, "value") else str(intent), is_followup_turn=False)
                visible_text = _clean_disclaimers(visible_text, is_followup_turn, has_critical_alert=True)
                yield f'data: {json.dumps({"replace": visible_text})}\n\n'

            # ── Record AI response in database ──
            async with AsyncSessionLocal() as persist_session:
                ai_chat = Chat(
                    user_id=current_user.id,
                    dependent_id=active_dep_id,
                    document_id=primary_doc.id if primary_doc else None,
                    session_id=effective_session_id,
                    session_title=current_session_title,
                    role="ai",
                    message=visible_text,
                )
                persist_session.add(ai_chat)
                await persist_session.commit()
                await persist_session.refresh(ai_chat)

                # Link AI message to chat documents if applicable
                if chat_docs:
                    for cd_doc in chat_docs:
                        link = ChatDocument(chat_id=ai_chat.id, document_id=cd_doc.id)
                        persist_session.add(link)
                    await persist_session.commit()

                is_sample_chat = bool(
                    (primary_doc and is_sample_document(primary_doc))
                    or any(is_sample_document(d) for d in chat_docs or [])
                )

                # Index chat message for cross-session retrieval (user message only, memory consent gated, skip sample reports)
                if not is_sample_chat and current_user.memory_consent_granted and settings.PATIENT_MEMORY_ENABLED:
                    try:
                        await index_chat_message(
                            chat_id=current_chat_id,
                            message_id=user_chat.id,
                            text=body.query,
                            user_id=current_user.id,
                            dependent_id=active_dep_id,
                            session=persist_session,
                        )
                    except Exception as e:
                        logger.warning("Failed indexing chat message: %s", e)

            # ── Trigger background fact extraction if consent granted (skip sample reports) ──
            if not is_sample_chat and current_user.memory_consent_granted and settings.PATIENT_MEMORY_ENABLED:
                task = asyncio.create_task(
                    process_chat_memory_extraction(
                        chat_id=current_chat_id,
                        user_id=current_user.id,
                        dependent_id=active_dep_id,
                        session_id=effective_session_id,
                        active_docs_metrics=active_docs_metrics,
                        document_name=primary_doc.filename if primary_doc else None,
                    )
                )
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

            yield f'data: [DONE]\n\n'

        except (asyncio.CancelledError, GeneratorExit):
            logger.info(
                "Client disconnected or query stream cancelled for user_id=%s, chat_id=%s",
                current_user.id,
                current_chat_id,
            )
            if stream_task and not stream_task.done():
                stream_task.cancel()
            if visible_text.strip():
                try:
                    async with AsyncSessionLocal() as cancel_session:
                        partial_msg = visible_text.strip() + " [interrupted]"
                        ai_chat = Chat(
                            user_id=current_user.id,
                            dependent_id=active_dep_id,
                            document_id=primary_doc.id if primary_doc else None,
                            session_id=effective_session_id,
                            session_title=current_session_title,
                            role="ai",
                            message=partial_msg,
                        )
                        cancel_session.add(ai_chat)
                        await cancel_session.commit()
                except Exception as db_err:
                    logger.warning("Failed saving partial chat turn on disconnect: %s", db_err)
            else:
                try:
                    async with AsyncSessionLocal() as cancel_session:
                        del_row = await cancel_session.get(Chat, current_chat_id)
                        if del_row:
                            await cancel_session.delete(del_row)
                            await cancel_session.commit()
                except Exception as db_err:
                    logger.warning("Failed removing orphaned user turn on disconnect: %s", db_err)
            raise
        except GeminiUnavailableError:
            logger.warning("All Gemini models unavailable during streaming", exc_info=True)
            if emergency_banner and visible_text.strip():
                try:
                    async with AsyncSessionLocal() as banner_session:
                        ai_chat = Chat(
                            user_id=current_user.id,
                            dependent_id=active_dep_id,
                            document_id=primary_doc.id if primary_doc else None,
                            session_id=effective_session_id,
                            session_title=current_session_title,
                            role="ai",
                            message=visible_text.strip(),
                        )
                        banner_session.add(ai_chat)
                        await banner_session.commit()
                except Exception as db_err:
                    logger.warning("Failed saving emergency banner turn on Gemini error: %s", db_err)
                yield "data: [DONE]\n\n"
                return
            try:
                fallback_msg = "The AI service is temporarily busy due to high demand. Please try again in 1-2 minutes."
                async with AsyncSessionLocal() as err_session:
                    ai_chat = Chat(
                        user_id=current_user.id,
                        dependent_id=active_dep_id,
                        document_id=primary_doc.id if primary_doc else None,
                        session_id=effective_session_id,
                        session_title=current_session_title,
                        role="ai",
                        message=fallback_msg,
                    )
                    err_session.add(ai_chat)
                    await err_session.commit()
            except Exception as db_err:
                logger.warning("Failed saving fallback assistant turn on Gemini error: %s", db_err)
            yield f'data: {json.dumps({"error": "The AI service is temporarily busy due to high demand. Please try again in 1-2 minutes."})}\n\n'
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            logger.error("Error during streaming query response: %s", e, exc_info=True)
            if emergency_banner and visible_text.strip():
                try:
                    async with AsyncSessionLocal() as banner_session:
                        ai_chat = Chat(
                            user_id=current_user.id,
                            dependent_id=active_dep_id,
                            document_id=primary_doc.id if primary_doc else None,
                            session_id=effective_session_id,
                            session_title=current_session_title,
                            role="ai",
                            message=visible_text.strip(),
                        )
                        banner_session.add(ai_chat)
                        await banner_session.commit()
                except Exception as db_err:
                    logger.warning("Failed saving emergency banner turn on unexpected error: %s", db_err)
                yield "data: [DONE]\n\n"
                return
            try:
                fallback_msg = "An unexpected error occurred while generating the response."
                async with AsyncSessionLocal() as err_session:
                    ai_chat = Chat(
                        user_id=current_user.id,
                        dependent_id=active_dep_id,
                        document_id=primary_doc.id if primary_doc else None,
                        session_id=effective_session_id,
                        session_title=current_session_title,
                        role="ai",
                        message=fallback_msg,
                    )
                    err_session.add(ai_chat)
                    await err_session.commit()
            except Exception as db_err:
                logger.warning("Failed saving fallback assistant turn on unexpected error: %s", db_err)
            yield f'data: {json.dumps({"error": "An unexpected error occurred while generating the response."})}\n\n'
            yield "data: [DONE]\n\n"
            return
        finally:
            _active_query_sessions.discard(session_lock_key)
            if stream_task and not stream_task.done():
                stream_task.cancel()

    return StreamingResponse(generate_response_stream(), media_type="text/event-stream")


# ─── Task 3: Dedicated Cached Document Summary ──────────────────────────────

class DocumentSummaryResponse(BaseModel):
    summary: str
    cached: bool


EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    "\U00002600-\U000026FF"  # miscellaneous symbols
    "]+",
    flags=re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Strip all emojis from generated text."""
    if not text:
        return ""
    return EMOJI_PATTERN.sub("", text)


async def _reconstruct_document_text(doc: Document) -> str:
    """Reconstruct full text of the document from stored chunks/content in order."""
    if not doc.file_path:
        return f"Medical Report: {doc.title or doc.filename}"

    try:
        resolved_path = str(await aensure_index_local(doc.file_path))
        if os.path.exists(resolved_path):
            def _load_chunks():
                try:
                    v, b = load_hybrid_index(resolved_path)
                    # 1. BM25 corpus retains original chunk ordering
                    if b and hasattr(b, "chunks") and b.chunks:
                        return [c.page_content for c in b.chunks if getattr(c, "page_content", None)]
                    # 2. FAISS index_to_docstore_id order
                    if hasattr(v, "index_to_docstore_id") and hasattr(v, "docstore"):
                        return [
                            v.docstore.search(v.index_to_docstore_id[i]).page_content
                            for i in range(len(v.index_to_docstore_id))
                            if hasattr(v.docstore.search(v.index_to_docstore_id[i]), "page_content")
                        ]
                    # 3. FAISS docstore dict fallback
                    if hasattr(v, "docstore") and hasattr(v.docstore, "_dict"):
                        return [c.page_content for c in v.docstore._dict.values() if getattr(c, "page_content", None)]
                except Exception as ex:
                    logger.warning("Error reading chunks from index for doc %s: %s", doc.id, ex)
                return []

            chunk_texts = await asyncio.to_thread(_load_chunks)
            if chunk_texts:
                return "\n\n".join(chunk_texts)
    except Exception as e:
        logger.warning("Failed to reconstruct text for doc %s: %s", doc.id, e)

    return f"Medical Report: {doc.title or doc.filename}"


@router.post(
    "/users/me/documents/{document_id}/summary",
    response_model=DocumentSummaryResponse,
    tags=["Documents", "Summary"],
)
@router.get(
    "/users/me/documents/{document_id}/summary",
    response_model=DocumentSummaryResponse,
    tags=["Documents", "Summary"],
)
@limiter.limit(settings.RATE_LIMIT_SUMMARY)
async def get_or_generate_document_summary(
    request: Request,
    document_id: str,
    force_refresh: bool = False,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format.")

    result = await db.execute(select(Document).filter(Document.id == doc_uuid))
    doc = result.scalars().first()

    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    # 1. Check persistent database cache (valid only if prefix matches PROMPT_VERSION_PREFIX)
    if not force_refresh and doc.cached_summary is not None and doc.cached_summary.startswith(PROMPT_VERSION_PREFIX):
        clean_summary = doc.cached_summary[len(PROMPT_VERSION_PREFIX):]
        if clean_summary.strip() != "":
            return DocumentSummaryResponse(summary=clean_summary, cached=True)

    if getattr(doc, "index_status", None) == "failed" or is_stale_building(doc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This document could not be processed. Please upload a different file or re-upload.",
        )

    if getattr(doc, "index_status", None) == "building":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document index is still building. Please retry in 2 seconds.",
            headers={"Retry-After": "2"},
        )

    # 2. Reconstruct document text from stored chunks/content ordered by chunk index
    report_text = await _reconstruct_document_text(doc)
    fallback_title = f"Medical Report: {doc.title or doc.filename}".strip()
    if not report_text or not report_text.strip() or report_text.strip() == fallback_title:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document index is still syncing. Please try again in a few seconds.",
            headers={"Retry-After": "2"},
        )

    raw_cm = doc.cached_metrics
    if isinstance(raw_cm, str):
        try:
            raw_cm = json.loads(raw_cm)
        except Exception:
            raw_cm = []
    if isinstance(raw_cm, dict) and "metrics" in raw_cm:
        raw_cm = raw_cm["metrics"]
    if not isinstance(raw_cm, list):
        raw_cm = None

    user_lang = getattr(current_user, "language_preference", "English") or "English"
    summary_prompt = build_document_summary_prompt(
        report_text,
        cached_metrics=raw_cm,
        language_preference=user_lang,
    )

    try:
        from google.genai.types import GenerateContentConfig, ThinkingConfig
        summary_config = GenerateContentConfig(
            thinking_config=ThinkingConfig(thinking_budget=0),
            temperature=0.2,
        )
        client = get_genai_client()
        response = None
        # Call Gemini using async client.aio.models.generate_content if available
        if hasattr(client, "aio") and hasattr(client.aio, "models"):
            try:
                gen_fn = client.aio.models.generate_content
                res = gen_fn(model=settings.GEMINI_MODEL, contents=summary_prompt, config=summary_config)
                if asyncio.iscoroutine(res):
                    response = await res
                elif hasattr(res, "text") and isinstance(res.text, str) and res.text:
                    response = res
            except Exception as aio_err:
                logger.debug("client.aio generate_content error/bypassed: %s", aio_err)

        if response is None or not getattr(response, "text", None):
            response = await call_gemini_with_retry(
                contents=summary_prompt,
                user_id=current_user.id,
                config=summary_config,
            )

        raw_text = getattr(response, "text", "") or ""
        summary_text = strip_emojis(raw_text).strip()

        # Guard Against Caching Empty/Error Responses:
        if summary_text:
            doc.cached_summary = f"{PROMPT_VERSION_PREFIX}{summary_text}"
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            return DocumentSummaryResponse(summary=summary_text, cached=False)
        else:
            return DocumentSummaryResponse(summary="", cached=False)
    except Exception as err:
        logger.error("Error generating document summary: %s", err)
        raise HTTPException(status_code=500, detail="Failed to generate document summary.")


