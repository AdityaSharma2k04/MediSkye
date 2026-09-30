from fastapi import APIRouter, Depends, Request, HTTPException, status
from google import genai
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langchain_community.vectorstores import FAISS

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import User, Document, Chat
from app.schemas.query import QueryRequest, QueryResponse, SourceChunk
from app.rag.prompt_builder import build_prompt, build_general_health_prompt
from app.rag.retriever import retrieve_relevant_docs
from app.rag.safety import append_disclaimer, get_emergency_response, is_emergency_query
from app.rag.embedder import get_embedder

router = APIRouter()


import json
from pydantic import BaseModel, Field
from typing import Optional
from fastapi.responses import StreamingResponse


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
    import uuid as uuid_mod
    try:
        doc_uuid = uuid_mod.UUID(document_id)
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


@router.post("/query", tags=["RAG Query"])
@limiter.limit(settings.RATE_LIMIT_QUERY)
async def query_bot(
    request: Request,
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    # ── Resolve document (may not exist for general-health queries) ──
    doc = None
    doc_id_valid = False
    try:
        doc_id = uuid.UUID(body.session_id)
        doc_id_valid = True
    except ValueError:
        pass  # Not a valid UUID → no document, treat as general-health

    if doc_id_valid:
        result = await db.execute(
            select(Document).filter(Document.id == doc_id, Document.user_id == current_user.id)
        )
        doc = result.scalars().first()

    has_document = doc is not None and bool(doc.file_path)

    # ── Intent Routing (document-aware) ──
    from app.rag.intent_router import classify_intent, QueryIntent

    if is_emergency_query(body.query):
        ai_msg = get_emergency_response()
        # Log emergency without document requirement
        if doc:
            user_chat = Chat(user_id=current_user.id, document_id=doc.id, role="user", message=body.query)
            db.add(user_chat)
            ai_chat = Chat(user_id=current_user.id, document_id=doc.id, role="ai", message=ai_msg)
            db.add(ai_chat)
        else:
            user_chat = Chat(user_id=current_user.id, document_id=None, role="user", message=body.query)
            db.add(user_chat)
            ai_chat = Chat(user_id=current_user.id, document_id=None, role="ai", message=ai_msg)
            db.add(ai_chat)
        await db.commit()

        async def emergency_stream():
            yield f'data: {json.dumps({"chunk": ai_msg})}\n\n'
            yield f'data: [DONE]\n\n'
        return StreamingResponse(emergency_stream(), media_type="text/event-stream")

    # Record user chat message (document_id may be None)
    user_chat = Chat(
        user_id=current_user.id,
        document_id=doc.id if doc else None,
        role="user",
        message=body.query
    )
    db.add(user_chat)
    await db.commit()

    intent = await classify_intent(body.query, has_document=has_document)

    # Guard: if intent is DOCUMENT_QA but no document is linked, downgrade
    if intent == QueryIntent.DOCUMENT_QA and not has_document:
        intent = QueryIntent.GENERAL_HEALTH

    # ── Active Profile & PHI Resolution (User or Dependent) ──
    from app.db.models import DependentProfile
    from app.services.patient_service import calculate_age

    active_profile = current_user
    active_dep_id = None

    target_patient_id = body.patient_id
    if not target_patient_id and doc and doc.dependent_id:
        target_patient_id = str(doc.dependent_id)

    if target_patient_id and target_patient_id.lower() != "self" and target_patient_id != str(current_user.id):
        try:
            p_uuid = uuid.UUID(target_patient_id)
            dep_res = await db.execute(
                select(DependentProfile).filter(
                    DependentProfile.id == p_uuid,
                    DependentProfile.user_id == current_user.id
                )
            )
            dep = dep_res.scalars().first()
            if dep:
                active_profile = dep
                active_dep_id = dep.id
        except ValueError:
            pass

    # Audit Logging with user_id and dependent_id
    from app.core.audit import log_audit
    await log_audit(db, "PHI_ACCESS_QUERY", current_user.id, "query_rag", request.client.host, dependent_id=active_dep_id)

    # Dynamic Age Calculation and Decrypted PHI attributes
    calc_age = calculate_age(active_profile.date_of_birth)
    calculated_age_str = f"{calc_age}" if calc_age is not None else "Unknown"
    biological_sex = active_profile.biological_sex or "Unspecified"
    pre_existing_conditions = active_profile.pre_existing_conditions or "None reported"
    current_medications = active_profile.current_medications or "None reported"
    language_preference = getattr(active_profile, "language_preference", None) or body.language or "English"

    async def generate_response_stream():
        full_text = ""
        try:
            client = genai.Client(api_key=settings.GOOGLE_API_KEY)

            if intent == QueryIntent.GENERAL_HEALTH:
                prompt = build_general_health_prompt(
                    user_query=body.query,
                    calculated_age=calculated_age_str,
                    biological_sex=biological_sex,
                    pre_existing_conditions=pre_existing_conditions,
                    current_medications=current_medications,
                    language_preference=language_preference,
                )
                yield f'data: {json.dumps({"sources": []})}\n\n'

            else:
                # DOCUMENT_QA — we know has_document is True at this point
                from app.rag.retriever import load_hybrid_index
                try:
                    vectorstore, bm25_index = load_hybrid_index(doc.file_path)
                except Exception as e:
                    yield f'data: {json.dumps({"error": "Could not load document index."})}\n\n'
                    return

                docs = retrieve_relevant_docs(body.query, vectorstore, bm25_index)
                prompt = build_prompt(
                    user_query=body.query,
                    retrieved_docs=docs,
                    calculated_age=calculated_age_str,
                    biological_sex=biological_sex,
                    pre_existing_conditions=pre_existing_conditions,
                    current_medications=current_medications,
                    language_preference=language_preference,
                )

                sources = [
                    SourceChunk(
                        title="Medical Report PDF",
                        page=d.metadata.get("page", 1),
                        score="98%",
                        excerpt=d.page_content[:140] + "...",
                    ).model_dump()
                    for d in docs[:3]
                ]
                yield f'data: {json.dumps({"sources": sources})}\n\n'

            # Stream generation
            response = client.models.generate_content_stream(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )

            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield f'data: {json.dumps({"chunk": chunk.text})}\n\n'

            disclaimer = "\n\n" + append_disclaimer("").strip()
            yield f'data: {json.dumps({"chunk": disclaimer})}\n\n'
            full_text += disclaimer

        except Exception as e:
            yield f'data: {json.dumps({"error": str(e)})}\n\n'
            return

        # Check for abnormal_flags
        import re
        import json as json_lib
        match = re.search(r'```json\s*(\{.*"abnormal_flags".*\})\s*```', full_text, re.DOTALL | re.IGNORECASE)
        if match:
            try:
                flags_data = json_lib.loads(match.group(1))
                abnormal_flags = flags_data.get("abnormal_flags", [])
                if abnormal_flags:
                    from app.rag.specialist_router import get_recommended_specialists
                    from app.db.database import AsyncSessionLocal
                    async with AsyncSessionLocal() as session:
                        specialists = await get_recommended_specialists(session, abnormal_flags)
                        if specialists:
                            yield f'data: {json.dumps({"specialists": specialists})}\n\n'
            except Exception:
                pass

        # Record AI Chat
        from app.db.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            ai_chat = Chat(
                user_id=current_user.id,
                document_id=doc.id if doc else None,
                role="ai",
                message=full_text
            )
            session.add(ai_chat)
            await session.commit()

        yield f'data: [DONE]\n\n'

    return StreamingResponse(generate_response_stream(), media_type="text/event-stream")
