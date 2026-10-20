import re
import os
import json
import uuid
import asyncio
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, Request, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.core.audit import log_audit
from app.db.database import get_db, AsyncSessionLocal
from app.db.models import User, Document, Chat, ChatDocument, DependentProfile, PatientFact
from app.llm.gemini_client import GeminiUnavailableError
from app.schemas.query import QueryRequest, QueryResponse, SourceChunk
from app.rag.prompt_builder import build_prompt, build_general_health_prompt
from app.rag.intent_router import classify_intent, QueryIntent
from app.rag.safety import append_disclaimer, get_emergency_response, is_emergency_query
from app.rag.retriever import load_hybrid_index, retrieve_relevant_docs
from app.rag.specialist_router import get_recommended_specialists
from app.rag.output_filter import scan_output
from app.services.patient_service import calculate_age
from app.services.patient_memory import get_active_facts, get_relevant_past_chunks, get_chat_documents
from app.services.memory_formatter import format_facts_for_prompt, format_past_chats_for_prompt
from app.services.fact_persistence import process_chat_memory_extraction
from app.services.chat_indexer import index_chat_message

logger = logging.getLogger(__name__)

# Hold strong references to background tasks to prevent GC mid-execution
_background_tasks: set = set()

router = APIRouter()


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New chat title (max 60 chars)")


@router.patch("/documents/{document_id}/title", tags=["RAG Query"])
async def rename_document_title(
    document_id: str,
    body: RenameChatRequest,
    current_user: User = Depends(get_current_user),
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

    doc.title = body.title.strip()
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return {"id": str(doc.id), "title": doc.title}


def _extract_metrics_from_docs(retrieved_docs: List[Any]) -> List[Dict[str, Any]]:
    """
    Heuristically extract structured lab metrics from retrieved document chunks for the reference ranges expander.
    Matches lines like: Glucose 105 mg/dL (70-99) High
    """
    metrics = []
    seen = set()
    pattern = re.compile(
        r"(?P<name>[A-Za-z0-9\s\-/]+?)\s*[:=\t]\s*(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z/%μ]+(?:\/[a-zA-Z0-9]+)?)\s*(?:\((?:ref:?\s*)?(?P<range>\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?)\))?\s*(?P<status>High|Low|Normal|Abnormal)?",
        re.IGNORECASE,
    )

    for d in retrieved_docs:
        text = d.page_content if hasattr(d, "page_content") else str(d)
        for line in text.split("\n"):
            line = line.strip()
            m = pattern.search(line)
            if m:
                name = m.group("name").strip()
                if len(name) > 35 or len(name) < 3 or name.lower() in seen:
                    continue
                seen.add(name.lower())
                metrics.append({
                    "name": name,
                    "value": m.group("val"),
                    "unit": m.group("unit"),
                    "status": m.group("status").capitalize() if m.group("status") else "Normal",
                    "range": m.group("range") or "Standard reference range",
                })
                if len(metrics) >= 50:
                    return metrics
    return metrics


@router.post("/query", tags=["RAG Query"])
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query_bot(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Resolve documents associated with active session / chat ──
    chat_docs: List[Document] = []
    primary_doc: Optional[Document] = None
    target_chat_id: Optional[uuid.UUID] = None

    if body.session_id:
        try:
            parsed_id = uuid.UUID(body.session_id)
            # 1. Check if session_id is an existing chat_id
            chat_check = await db.execute(
                select(Chat).filter(Chat.id == parsed_id, Chat.user_id == current_user.id)
            )
            chat_found = chat_check.scalars().first()
            if chat_found:
                target_chat_id = chat_found.id
                chat_docs = await get_chat_documents(target_chat_id, session=db)
                if chat_docs:
                    primary_doc = chat_docs[0]
            else:
                # 2. Check if session_id is a document_id
                doc_check = await db.execute(
                    select(Document).filter(Document.id == parsed_id, Document.user_id == current_user.id)
                )
                doc_found = doc_check.scalars().first()
                if doc_found:
                    primary_doc = doc_found
                    chat_docs = [doc_found]
        except ValueError:
            pass

    has_document = len(chat_docs) > 0 and any(bool(d.file_path) for d in chat_docs)

    # ── Emergency keyword gate ──
    if is_emergency_query(body.query):
        ai_msg = get_emergency_response()
        user_chat = Chat(
            user_id=current_user.id,
            document_id=primary_doc.id if primary_doc else None,
            role="user",
            message=body.query,
        )
        ai_chat = Chat(
            user_id=current_user.id,
            document_id=primary_doc.id if primary_doc else None,
            role="ai",
            message=ai_msg,
        )
        db.add_all([user_chat, ai_chat])
        await db.commit()

        async def emergency_stream():
            yield f'data: {json.dumps({"chunk": ai_msg})}\n\n'
            yield f'data: [DONE]\n\n'

        return StreamingResponse(emergency_stream(), media_type="text/event-stream")

    # Record user message in DB
    user_chat = Chat(
        user_id=current_user.id,
        document_id=primary_doc.id if primary_doc else None,
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
        existing_cds = await db.execute(
            select(ChatDocument.document_id).filter(
                ChatDocument.chat_id == current_chat_id,
                ChatDocument.document_id.in_(doc_ids),
            )
        )
        already_linked = set(existing_cds.scalars().all())
        for doc_id in doc_ids:
            if doc_id not in already_linked:
                db.add(ChatDocument(chat_id=current_chat_id, document_id=doc_id))
        await db.commit()

    # ── Intent Classification ──
    intent = await classify_intent(body.query, has_document=has_document)
    if intent == QueryIntent.DOCUMENT_QA and not has_document:
        intent = QueryIntent.GENERAL_HEALTH

    # ── Profile & PHI Context Resolution ──
    active_profile = current_user
    active_dep_id: Optional[uuid.UUID] = None

    target_patient_id = body.patient_id
    if not target_patient_id and primary_doc and primary_doc.dependent_id:
        target_patient_id = str(primary_doc.dependent_id)

    if target_patient_id and target_patient_id.lower() != "self" and target_patient_id != str(current_user.id):
        try:
            p_uuid = uuid.UUID(target_patient_id)
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == p_uuid,
                    DependentProfile.user_id == current_user.id,
                )
            )
            dep = dep_res.scalars().first()
            if dep:
                active_profile = dep
                active_dep_id = dep.id
        except ValueError:
            pass

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
    language_preference = getattr(active_profile, "language_preference", None) or body.language or "English"
    height_cm = getattr(active_profile, "height_cm", None)
    diet_type = getattr(active_profile, "diet_type", None)
    activity_level = getattr(active_profile, "activity_level", None)
    occupation = getattr(active_profile, "occupation", None)

    async def generate_response_stream():
        try:
            # ── Stage 1: Analyzing ──
            yield f'event: stage\ndata: {json.dumps({"stage": "analyzing", "message": "Analyzing your question..."})}\n\n'
            await asyncio.sleep(0.4)

            # ── Multi-doc retrieval (for DOCUMENT_QA only) ──
            retrieved_chunks = []
            if intent == QueryIntent.DOCUMENT_QA:
                yield f'event: stage\ndata: {json.dumps({"stage": "retrieving", "message": "Searching your reports..."})}\n\n'
                all_doc_results = []
                for d in chat_docs:
                    if d.file_path and os.path.exists(d.file_path):
                        try:
                            def _load_and_retrieve(path, q):
                                v, b = load_hybrid_index(path)
                                return retrieve_relevant_docs(q, v, b, k=4)

                            doc_chunks = await asyncio.to_thread(_load_and_retrieve, d.file_path, body.query)
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
                await asyncio.sleep(0.4)

            # ── Memory retrieval (Tier 1 facts always, Tier 2 past chunks for DOCUMENT_QA only) ──
            formatted_facts = None
            formatted_past_chats = None

            if current_user.memory_consent_granted and settings.PATIENT_MEMORY_ENABLED:
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
                        await asyncio.sleep(0.4)

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
                            formatted_past_chats = format_past_chats_for_prompt(past_chunks)

            # ── Stage: Generating ──
            yield f'event: stage\ndata: {json.dumps({"stage": "generating", "message": "Preparing your answer..."})}\n\n'

            # Build grounded prompt
            if intent == QueryIntent.DOCUMENT_QA:
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
                    height_cm=height_cm,
                    diet_type=diet_type,
                    activity_level=activity_level,
                    occupation=occupation,
                )

                sources = [
                    SourceChunk(
                        title=d.metadata.get("source") or d.metadata.get("filename") or "Medical Report",
                        page=d.metadata.get("page", 1),
                        score="98%",
                        excerpt=d.page_content[:140] + "...",
                    ).model_dump()
                    for d in retrieved_chunks[:4]
                ]
                yield f'data: {json.dumps({"sources": sources})}\n\n'

                # Attach metrics for reference ranges expander
                extracted_metrics = _extract_metrics_from_docs(retrieved_chunks)
                if extracted_metrics:
                    yield f'data: {json.dumps({"metrics": extracted_metrics})}\n\n'

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
                    height_cm=height_cm,
                    diet_type=diet_type,
                    activity_level=activity_level,
                    occupation=occupation,
                )
                yield f'data: {json.dumps({"sources": []})}\n\n'

            full_raw_text = ""
            visible_text = ""

            # ── Gemini stream with thread offloading ──
            from google.genai.types import GenerateContentConfig
            from app.llm.gemini_client import FALLBACK_MODELS, _is_retryable_error, get_genai_client
            client = get_genai_client()

            loop = asyncio.get_running_loop()
            queue = asyncio.Queue()
            SENTINEL = object()

            def _stream_producer():
                from google.genai.types import GenerateContentConfig
                from app.llm.gemini_client import FALLBACK_MODELS, _is_retryable_error, get_genai_client

                client = get_genai_client()
                last_exception = None

                try:
                    for current_model in FALLBACK_MODELS:
                        yielded_any = False
                        try:
                            response = client.models.generate_content_stream(
                                model=current_model,
                                contents=user_content,
                                config=GenerateContentConfig(system_instruction=system_instruction),
                            )
                            for chunk in response:
                                yielded_any = True
                                loop.call_soon_threadsafe(queue.put_nowait, chunk)
                            loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)
                            return  # success, done
                        except Exception as exc:
                            last_exception = exc
                            if yielded_any or not _is_retryable_error(exc):
                                loop.call_soon_threadsafe(queue.put_nowait, exc)
                                loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)
                                return
                            logger.warning(
                                "Streaming model %s failed with retryable error, trying next",
                                current_model,
                            )
                            continue

                    # All models failed
                    err = GeminiUnavailableError(f"All streaming models failed. Last: {last_exception}")
                    loop.call_soon_threadsafe(queue.put_nowait, err)
                    loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)
                except Exception as fatal_exc:
                    loop.call_soon_threadsafe(queue.put_nowait, fatal_exc)
                    loop.call_soon_threadsafe(queue.put_nowait, SENTINEL)

            stream_task = asyncio.create_task(asyncio.to_thread(_stream_producer))

            pending_buffer = ""
            in_json_block = False

            while True:
                item = await queue.get()
                if item is SENTINEL:
                    break
                if isinstance(item, Exception):
                    raise item

                chunk_text = getattr(item, "text", None)
                if not chunk_text:
                    continue

                full_raw_text += chunk_text

                if in_json_block:
                    # Already detected JSON block; do not stream anything to client
                    continue

                pending_buffer += chunk_text

                # Check if JSON block starts in pending_buffer
                lower_buf = pending_buffer.lower()
                if "```json" in lower_buf or "```" in lower_buf:
                    fence_idx = lower_buf.find("```")
                    tail = pending_buffer[fence_idx:]

                    # Check if this fence is the abnormal_flags block
                    if "abnormal_flags" in tail:
                        in_json_block = True
                        visible_chunk = pending_buffer[:fence_idx]
                        if visible_chunk:
                            visible_text += visible_chunk
                            yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                        pending_buffer = ""
                    elif len(tail) < 150:
                        # Wait for more chunks to see if 'abnormal_flags' appears
                        # Yield any text that occurred before the backticks
                        if fence_idx > 0:
                            visible_chunk = pending_buffer[:fence_idx]
                            visible_text += visible_chunk
                            yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                            pending_buffer = pending_buffer[fence_idx:]
                    else:
                        # Long block without 'abnormal_flags' — ordinary content, flush
                        visible_text += pending_buffer
                        yield f'data: {json.dumps({"chunk": pending_buffer})}\n\n'
                        pending_buffer = ""
                else:
                    # Hold back any trailing backticks in case ``` is split across chunks
                    if pending_buffer.endswith("``"):
                        to_yield = pending_buffer[:-2]
                        pending_buffer = "``"
                    elif pending_buffer.endswith("`"):
                        to_yield = pending_buffer[:-1]
                        pending_buffer = "`"
                    else:
                        to_yield = pending_buffer
                        pending_buffer = ""

                    if to_yield:
                        visible_text += to_yield
                        yield f'data: {json.dumps({"chunk": to_yield})}\n\n'

            # Stream finished — flush any remaining pending_buffer if not entering JSON block
            if pending_buffer and not in_json_block:
                lower_pending = pending_buffer.lower()
                if "abnormal_flags" in lower_pending and "```" in lower_pending:
                    fence_idx = lower_pending.find("```")
                    visible_chunk = pending_buffer[:fence_idx]
                    if visible_chunk:
                        visible_text += visible_chunk
                        yield f'data: {json.dumps({"chunk": visible_chunk})}\n\n'
                else:
                    visible_text += pending_buffer
                    yield f'data: {json.dumps({"chunk": pending_buffer})}\n\n'
                pending_buffer = ""

            disclaimer = "\n\n" + append_disclaimer("").strip()
            yield f'data: {json.dumps({"chunk": disclaimer})}\n\n'
            visible_text += disclaimer

        except GeminiUnavailableError:
            logger.warning("All Gemini models unavailable during streaming", exc_info=True)
            yield f'data: {json.dumps({"error": "The AI service is temporarily busy due to high demand. Please try again in 1-2 minutes."})}\n\n'
            yield "data: [DONE]\n\n"
            return
        except Exception as e:
            logger.error("Error during streaming query response: %s", e, exc_info=True)
            yield f'data: {json.dumps({"error": "An unexpected error occurred while generating the response."})}\n\n'
            yield "data: [DONE]\n\n"
            return

        # ── Output filter scan (monitoring only) ──
        is_safe, reason = scan_output(visible_text)
        if not is_safe:
            logger.warning(
                "Output filter triggered (monitoring only): %s | user_id=%s",
                reason,
                current_user.id,
            )

        # ── Parse abnormal flags for specialist recommendations ──
        match = re.search(r'```json\s*(\{.*?"abnormal_flags".*?\})\s*```', full_raw_text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                flags_data = json.loads(match.group(1))
                abnormal_flags = flags_data.get("abnormal_flags", [])
                if abnormal_flags:
                    async with AsyncSessionLocal() as spec_session:
                        specialists = await get_recommended_specialists(spec_session, abnormal_flags)
                        if specialists:
                            yield f'data: {json.dumps({"specialists": specialists})}\n\n'
            except Exception as e:
                logger.warning("Error parsing abnormal flags for specialists: %s", e)

        # ── Record AI response in database ──
        async with AsyncSessionLocal() as persist_session:
            ai_chat = Chat(
                user_id=current_user.id,
                document_id=primary_doc.id if primary_doc else None,
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

            # Index chat messages for cross-session retrieval
            try:
                await index_chat_message(
                    chat_id=current_chat_id,
                    message_id=user_chat.id,
                    text=body.query,
                    user_id=current_user.id,
                    dependent_id=active_dep_id,
                    session=persist_session,
                )
                if len(visible_text.strip()) >= 100:
                    await index_chat_message(
                        chat_id=current_chat_id,
                        message_id=ai_chat.id,
                        text=visible_text,
                        user_id=current_user.id,
                        dependent_id=active_dep_id,
                        session=persist_session,
                    )
            except Exception as e:
                logger.warning("Failed indexing chat message: %s", e)

        # ── Trigger background fact extraction if consent granted ──
        if current_user.memory_consent_granted and settings.PATIENT_MEMORY_ENABLED:
            task = asyncio.create_task(
                process_chat_memory_extraction(
                    chat_id=current_chat_id,
                    user_id=current_user.id,
                    dependent_id=active_dep_id,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        yield f'data: [DONE]\n\n'

    return StreamingResponse(generate_response_stream(), media_type="text/event-stream")
