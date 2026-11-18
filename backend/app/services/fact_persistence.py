import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import Chat, ChatDocument, Document, PatientFact, User
from app.services.fact_extractor import extract_facts
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


def _compute_fact_key(fact_type: str, fact_text: str) -> str:
    """Generate a clean slug for indexing and identifying biomarker/condition keys."""
    clean = re.sub(r"\s*\[Source Report:[^\]]+\]", "", fact_text, flags=re.IGNORECASE).strip()
    if ":" in clean:
        key_prefix = clean.split(":", 1)[0].strip()
    else:
        key_prefix = clean
    key_slug = re.sub(r"[^a-zA-Z0-9]+", "_", key_prefix).strip("_").lower()
    return f"{fact_type.lower()}:{key_slug[:50]}"


async def save_facts(
    extraction_result: dict[str, Any],
    user_id: Any,
    dependent_id: Any | None,
    source_chat_id: Any | None,
    session: AsyncSession,
    source_document_name: str | None = None,
    source_type: str = "chat",
    source_id: str | None = None,
) -> dict[str, int]:
    """
    Persist extracted facts and handle retractions in a single transaction with retry:
    - Retractions: mark is_active = False (never hard-deleted).
    - Near-duplicates: update last_seen_at instead of inserting.
    - Preserves distinct measurements across different reports.
    - Retries transaction commit on database contention.
    Returns: {"inserted": N, "retracted": M, "updated": K}
    """
    inserted = 0
    retracted = 0
    updated = 0

    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
    s_type = source_type or "chat"
    s_id = str(source_id) if source_id else (str(source_chat_id) if source_chat_id else None)

    # Handle retractions first (single batch query)
    retraction_items = extraction_result.get("retractions", [])
    valid_retraction_uuids = []
    for ret in retraction_items:
        ret_id_raw = ret.get("existing_fact_id")
        if not ret_id_raw:
            continue
        try:
            valid_retraction_uuids.append(uuid.UUID(str(ret_id_raw)))
        except (ValueError, TypeError) as e:
            logger.warning("Error parsing retraction fact_id %s: %s", ret_id_raw, e)

    if valid_retraction_uuids:
        try:
            dep_filter = PatientFact.dependent_id == d_id if d_id else PatientFact.dependent_id.is_(None)
            q = select(PatientFact).filter(
                PatientFact.id.in_(valid_retraction_uuids),
                PatientFact.user_id == u_id,
                dep_filter,
                PatientFact.is_user_verified.is_(False),
                func.lower(PatientFact.fact_type).notin_(("allergy", "medication", "condition")),
            )
            res = await session.execute(q)
            target_facts = res.scalars().all()
            for target_fact in target_facts:
                if target_fact.is_active:
                    target_fact.is_active = False
                    target_fact.last_seen_at = datetime.now(UTC)
                    retracted += 1
        except Exception as e:
            logger.warning("Error processing batch retractions: %s", e)

    # Fetch existing active facts for deduplication/update
    existing_query = select(PatientFact).filter(
        PatientFact.user_id == u_id,
        PatientFact.dependent_id == d_id if d_id else PatientFact.dependent_id.is_(None),
        PatientFact.is_active.is_(True),
    )
    res_existing = await session.execute(existing_query)
    active_facts = list(res_existing.scalars().all())

    now = datetime.now(UTC)
    facts_to_process = extraction_result.get("facts", [])

    for fact in facts_to_process:
        fact_type = (fact.get("type") or fact.get("fact_type") or "").strip()
        fact_text = (fact.get("text") or fact.get("fact_text") or "").strip()
        if not fact_type or not fact_text:
            continue

        # Task 4: In chat sessions where a document is attached, never re-extract measurements
        if source_type == "chat" and source_document_name and fact_type.lower() == "measurement":
            continue

        # Task 4: Never save physician / doctor names as family history or patient facts
        lower_fact = fact_text.lower()
        if any(w in lower_fact for w in ("dr.", "dr ", "doctor", "physician", "sethi", "kulkarni", "bhandari")) and (
            fact_type.lower() == "family_history" or "doctor" in lower_fact or "physician" in lower_fact
        ):
            continue

        # Task 4: Never extract weight/height echoes from assistant chat turns
        if fact_type.lower() in ("weight", "measurement") and source_type == "chat":
            if re.search(r"weighs?\s+[0-9]+(?:\.[0-9]+)?\s*kg", fact_text, re.IGNORECASE):
                continue

        # Attach exact source document name if available and not already formatted
        if source_document_name and "[Source Report:" not in fact_text:
            fact_text = f"{fact_text} [Source Report: {source_document_name}]"

        confidence = float(fact.get("confidence", 0.85))
        excerpt = fact.get("excerpt")
        fact_key_val = fact.get("key") or _compute_fact_key(fact_type, fact_text)

        matched_existing: PatientFact | None = None
        clean_new = re.sub(r"\s*\[Source Report:[^\]]+\]", "", fact_text, flags=re.IGNORECASE).strip().lower()

        for ef in active_facts:
            if ef.fact_type.lower() != fact_type.lower():
                continue
            clean_ef = re.sub(r"\s*\[Source Report:[^\]]+\]", "", ef.fact_text, flags=re.IGNORECASE).strip().lower()

            # For durable qualitative health context (condition, allergy, lifestyle, family_history, sport_hobby):
            # deduplicate by semantic fact content regardless of source document
            if fact_type.lower() in ("condition", "allergy", "lifestyle", "family_history", "sport_hobby"):
                if clean_ef == clean_new or ef.fact_text.strip().lower() == fact_text.lower():
                    matched_existing = ef
                    break
            else:
                # For quantitative measurements / weights:
                # If exact full text match (including source report)
                if ef.fact_text.strip().lower() == fact_text.lower():
                    matched_existing = ef
                    break
                # If the test & value are the same: check if they belong to the same source document
                elif clean_ef == clean_new:
                    if source_document_name and f"[source report: {source_document_name.strip().lower()}]" in ef.fact_text.lower() or not source_document_name and not re.search(r"\[Source Report:", ef.fact_text, re.IGNORECASE):
                        matched_existing = ef
                        break

        if matched_existing:
            matched_existing.last_seen_at = now
            matched_existing.is_active = True
            matched_existing.confidence = max(matched_existing.confidence, confidence)
            if not matched_existing.fact_key:
                matched_existing.fact_key = fact_key_val
            # If existing fact did not have source report attribution, add it
            if source_document_name and "[Source Report:" not in matched_existing.fact_text:
                matched_existing.fact_text = f"{matched_existing.fact_text} [Source Report: {source_document_name}]"
            updated += 1
        else:
            new_fact = PatientFact(
                user_id=u_id,
                dependent_id=d_id,
                fact_type=fact_type,
                fact_key=fact_key_val,
                fact_text=fact_text,
                confidence=confidence,
                is_active=True,
                is_user_verified=False,
                source_type=s_type,
                source_id=s_id,
                source_excerpt=excerpt,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
            )
            session.add(new_fact)
            active_facts.append(new_fact)
            inserted += 1

    # 3-attempt DB transaction commit retry on contention/locks
    for db_attempt in range(1, 4):
        try:
            await session.commit()
            break
        except Exception as db_err:
            await session.rollback()
            if db_attempt == 3:
                logger.error("Failed committing facts to DB after 3 attempts: %s", db_err, exc_info=True)
                raise
            logger.warning("DB contention during save_facts (attempt %d/3): %s. Retrying...", db_attempt, db_err)
            await asyncio.sleep(0.15 * db_attempt)

    return {"inserted": inserted, "retracted": retracted, "updated": updated}


async def process_chat_memory_extraction(
    chat_id: Any,
    user_id: Any,
    dependent_id: Any | None = None,
    session_id: str | None = None,
    active_docs_metrics: list[dict[str, Any]] | None = None,
    document_name: str | None = None,
) -> None:
    """
    Background worker:
    1. Fetches last 6 messages from the specific conversation session.
    2. Loads linked document cached_metrics (out-of-range & near-boundary markers) for full clinical context.
    3. Fetches existing active facts.
    4. Calls extract_facts().
    5. Calls save_facts().
    Safe fail — logs errors, never raises.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Check user consent
            u_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            user_res = await session.execute(select(User).filter(User.id == u_uuid))
            user = user_res.scalars().first()
            if not user or not user.memory_consent_granted or not settings.PATIENT_MEMORY_ENABLED:
                logger.info("Skipping memory extraction: memory consent not granted for user %s", user_id)
                return

            # Fetch last 6 messages scoped strictly to the specific conversation session
            chat_filters = [Chat.user_id == u_uuid]
            if session_id:
                chat_filters.append(Chat.session_id == session_id)
            elif chat_id:
                try:
                    c_uuid = uuid.UUID(str(chat_id))
                    target_chat = await session.get(Chat, c_uuid)
                    if target_chat is not None:
                        if target_chat.session_id:
                            chat_filters.append(Chat.session_id == target_chat.session_id)
                        elif target_chat.document_id is not None:
                            chat_filters.append(Chat.document_id == target_chat.document_id)
                        else:
                            chat_filters.append(Chat.document_id.is_(None))
                    else:
                        chat_filters.append(Chat.document_id == c_uuid)
                except (ValueError, TypeError) as cid_err:
                    logger.debug("Non-UUID chat_id passed to process_chat_memory_extraction: %s", cid_err)

            msg_res = await session.execute(
                select(Chat)
                .filter(*chat_filters)
                .order_by(Chat.created_at.desc())
                .limit(6)
            )
            chats = msg_res.scalars().all()
            chats = list(reversed(chats))  # Chronological order

            if not chats:
                return

            # Resolve associated source documents
            linked_docs = []
            for c in chats:
                if c.document_id:
                    doc_res = await session.execute(select(Document).filter(Document.id == c.document_id))
                    d = doc_res.scalars().first()
                    if d and d not in linked_docs:
                        linked_docs.append(d)

            if not linked_docs and chats:
                chat_ids = [c.id for c in chats if c.id]
                cd_res = await session.execute(
                    select(Document)
                    .join(ChatDocument, ChatDocument.document_id == Document.id)
                    .filter(ChatDocument.chat_id.in_(chat_ids))
                    .order_by(ChatDocument.added_at.desc())
                )
                for d in cd_res.scalars().all():
                    if d not in linked_docs:
                        linked_docs.append(d)

            if not linked_docs and chat_id:
                try:
                    c_uuid = uuid.UUID(str(chat_id))
                    doc_check = await session.execute(select(Document).filter(Document.id == c_uuid))
                    d = doc_check.scalars().first()
                    if d and d not in linked_docs:
                        linked_docs.append(d)
                except (ValueError, TypeError):
                    pass

            primary_doc = linked_docs[0] if linked_docs else None
            source_doc_name = document_name or ((primary_doc.filename or primary_doc.title) if primary_doc else None)

            from app.services.clinical_units import is_sample_document
            if (
                any(is_sample_document(d) for d in linked_docs)
                or (primary_doc and is_sample_document(primary_doc))
                or is_sample_document(source_doc_name)
            ):
                logger.debug("Skipping chat memory extraction for sample report: session_id=%s, doc=%s", session_id, source_doc_name)
                return

            # Build clinical metrics context from active_docs_metrics or linked document cached_metrics
            doc_context_items = []
            metrics_source = active_docs_metrics
            if not metrics_source and linked_docs:
                for doc in linked_docs:
                    raw_cm = doc.cached_metrics
                    if isinstance(raw_cm, str):
                        try:
                            raw_cm = json.loads(raw_cm)
                        except Exception:
                            raw_cm = []
                    if isinstance(raw_cm, dict) and "metrics" in raw_cm:
                        raw_cm = raw_cm["metrics"]
                    if isinstance(raw_cm, list) and raw_cm:
                        metrics_source = raw_cm
                        break

            if metrics_source:
                flagged_or_near = []
                for m in metrics_source:
                    if isinstance(m, dict):
                        status = str(m.get("status") or "").lower()
                        test = m.get("test") or m.get("name") or ""
                        val = m.get("value") or ""
                        unit = m.get("unit") or ""
                        rng = m.get("range") or m.get("reference_range") or ""
                        # Include out-of-range, near-boundary, or any flagged metric (or all if small panel)
                        if any(s in status for s in ["high", "low", "abnormal", "critical", "borderline", "near"]):
                            flagged_or_near.append(f"- {test}: {val} {unit} ({status.upper()}, Ref: {rng})")
                        elif len(metrics_source) <= 12:
                            flagged_or_near.append(f"- {test}: {val} {unit} (Ref: {rng})")

                if flagged_or_near:
                    doc_label = source_doc_name or "Report"
                    doc_context_items.append(f"[Document Findings: {doc_label}]\n" + "\n".join(flagged_or_near))

            messages_for_extraction = list(chats)
            # Only include doc context for standalone chats (without attached report) where doc facts are not already locked at upload time
            if doc_context_items and not primary_doc and not source_doc_name:
                messages_for_extraction.append({
                    "role": "system",
                    "content": "Active Medical Report Biomarkers:\n" + "\n\n".join(doc_context_items),
                })

            # Fetch existing active facts
            d_uuid = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
            facts_res = await session.execute(
                select(PatientFact).filter(
                    PatientFact.user_id == u_uuid,
                    PatientFact.dependent_id == d_uuid if d_uuid else PatientFact.dependent_id.is_(None),
                    PatientFact.is_active.is_(True),
                )
            )
            existing_facts = facts_res.scalars().all()

            extraction_result = await extract_facts(
                messages=messages_for_extraction,
                existing_facts=existing_facts,
                user_id=u_uuid,
                dependent_id=d_uuid,
                document_name=source_doc_name,
            )

            stats = await save_facts(
                extraction_result=extraction_result,
                user_id=u_uuid,
                dependent_id=d_uuid,
                source_chat_id=chat_id,
                session=session,
                source_document_name=source_doc_name,
                source_type="chat",
                source_id=str(chat_id) if chat_id else None,
            )
            logger.info("Fact persistence completed for user %s: %s", user_id, stats)

    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        logger.error("Failed to run background memory extraction: %s", e, exc_info=True)


async def process_document_memory_extraction(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    dependent_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """
    Auto-extract durable clinical facts directly from an uploaded report when metrics cache warming completes.
    Gated on user's memory_consent_granted == True and settings.PATIENT_MEMORY_ENABLED.
    Links extracted facts with source_type='document' and source_id=str(doc_id).
    """
    try:
        async with AsyncSessionLocal() as session:
            u_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            user_res = await session.execute(select(User).filter(User.id == u_uuid))
            user = user_res.scalars().first()
            if not user or not user.memory_consent_granted or not settings.PATIENT_MEMORY_ENABLED:
                logger.info("Skipping document memory extraction: memory consent not granted for user %s", user_id)
                return {"inserted": 0, "retracted": 0, "updated": 0}

            d_uuid = uuid.UUID(str(doc_id)) if isinstance(doc_id, str) else doc_id
            doc_res = await session.execute(select(Document).filter(Document.id == d_uuid))
            doc = doc_res.scalars().first()
            if not doc:
                logger.warning("Document %s not found for memory extraction", doc_id)
                return {"inserted": 0, "retracted": 0, "updated": 0}

            from app.services.clinical_units import is_sample_document
            if is_sample_document(doc):
                logger.debug("Skipping document memory extraction for sample document %s", doc_id)
                return {"inserted": 0, "retracted": 0, "updated": 0}

            dep_uuid = dependent_id or doc.dependent_id
            if dep_uuid and isinstance(dep_uuid, str):
                dep_uuid = uuid.UUID(dep_uuid)

            doc_name = doc.filename or doc.title or "Lab Report"

            # Parse cached_metrics
            raw_cm = doc.cached_metrics
            if isinstance(raw_cm, str):
                try:
                    raw_cm = json.loads(raw_cm)
                except Exception:
                    raw_cm = []
            if isinstance(raw_cm, dict) and "metrics" in raw_cm:
                raw_cm = raw_cm["metrics"]
            if not isinstance(raw_cm, list):
                raw_cm = []

            metric_lines = []
            for m in raw_cm:
                if isinstance(m, dict):
                    test = m.get("test") or m.get("name") or ""
                    val = m.get("value") or ""
                    unit = m.get("unit") or ""
                    rng = m.get("range") or m.get("reference_range") or ""
                    status = str(m.get("status") or "Normal").strip()
                    if test and val:
                        metric_lines.append(f"- {test}: {val} {unit} (Reference: {rng}, Status: {status})")

            # Fetch a sample of document text from chunks if available
            doc_text = ""
            try:
                from app.rag.bm25 import get_docstore
                docstore = get_docstore()
                chunks = docstore.get_chunks_for_doc(d_uuid)
                if chunks:
                    doc_text = "\n".join(c.text for c in chunks[:5])
            except Exception as e:
                logger.debug("Could not fetch docstore chunks for doc %s: %s", doc_id, e)

            content_parts = [f"Lab Report: {doc_name}"]
            if doc.created_at:
                content_parts.append(f"Date: {doc.created_at.strftime('%Y-%m-%d')}")
            if metric_lines:
                content_parts.append("Measured Biomarkers:\n" + "\n".join(metric_lines))
            if doc_text:
                content_parts.append("Report Content Excerpt:\n" + doc_text[:1500])

            doc_content = "\n\n".join(content_parts)
            messages = [
                {
                    "role": "user",
                    "content": f"Please extract key medical facts and measurements from this report:\n\n{doc_content}",
                }
            ]

            # Fetch existing active facts for deduplication
            facts_res = await session.execute(
                select(PatientFact).filter(
                    PatientFact.user_id == u_uuid,
                    PatientFact.dependent_id == dep_uuid if dep_uuid else PatientFact.dependent_id.is_(None),
                    PatientFact.is_active.is_(True),
                )
            )
            existing_facts = facts_res.scalars().all()

            extraction_result = await extract_facts(
                messages=messages,
                existing_facts=existing_facts,
                user_id=u_uuid,
                dependent_id=dep_uuid,
                document_name=doc_name,
            )

            stats = await save_facts(
                extraction_result=extraction_result,
                user_id=u_uuid,
                dependent_id=dep_uuid,
                source_chat_id=None,
                session=session,
                source_document_name=doc_name,
                source_type="document",
                source_id=str(d_uuid),
            )
            logger.info("Document memory extraction completed for doc %s (user %s): %s", doc_id, user_id, stats)
            return stats

    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        logger.error("Failed to run document memory extraction for doc %s: %s", doc_id, e, exc_info=True)
        return {"inserted": 0, "retracted": 0, "updated": 0}
