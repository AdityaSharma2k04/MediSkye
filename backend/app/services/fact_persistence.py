import uuid
import logging
from datetime import datetime, UTC
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import PatientFact, Chat, User
from app.db.database import AsyncSessionLocal
from app.services.fact_extractor import extract_facts

logger = logging.getLogger(__name__)


async def save_facts(
    extraction_result: Dict[str, Any],
    user_id: Any,
    dependent_id: Optional[Any],
    source_chat_id: Optional[Any],
    session: AsyncSession,
) -> Dict[str, int]:
    """
    Persist extracted facts and handle retractions in a single transaction:
    - Retractions: mark is_active = False (never hard-deleted).
    - Near-duplicates: update last_seen_at instead of inserting.
    - New facts: insert with source_type='chat', source_id=chat_id.
    Returns: {"inserted": N, "retracted": M, "updated": K}
    """
    inserted = 0
    retracted = 0
    updated = 0

    u_id = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
    c_id_str = str(source_chat_id) if source_chat_id else None

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
            q = select(PatientFact).filter(
                PatientFact.id.in_(valid_retraction_uuids),
                PatientFact.user_id == u_id,
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
    active_facts = res_existing.scalars().all()

    now = datetime.now(UTC)
    facts_to_process = extraction_result.get("facts", [])

    for fact in facts_to_process:
        fact_type = (fact.get("type") or fact.get("fact_type") or "").strip()
        fact_text = (fact.get("text") or fact.get("fact_text") or "").strip()
        if not fact_type or not fact_text:
            continue

        confidence = float(fact.get("confidence", 1.0))
        excerpt = fact.get("excerpt")

        # Check for near-duplicate among active facts of same type
        matched_existing: Optional[PatientFact] = None
        for ef in active_facts:
            if ef.fact_type.lower() == fact_type.lower():
                if ef.fact_text.strip().lower() == fact_text.lower():
                    matched_existing = ef
                    break

        if matched_existing:
            matched_existing.last_seen_at = now
            if confidence > matched_existing.confidence:
                matched_existing.confidence = confidence
            updated += 1
        else:
            new_fact = PatientFact(
                user_id=u_id,
                dependent_id=d_id,
                fact_type=fact_type,
                fact_text=fact_text,
                confidence=confidence,
                is_active=True,
                is_user_verified=False,
                source_type="chat",
                source_id=c_id_str,
                source_excerpt=excerpt,
                first_seen_at=now,
                last_seen_at=now,
                created_at=now,
            )
            session.add(new_fact)
            active_facts.append(new_fact)
            inserted += 1

    await session.commit()
    return {"inserted": inserted, "retracted": retracted, "updated": updated}


async def process_chat_memory_extraction(
    chat_id: Any,
    user_id: Any,
    dependent_id: Optional[Any] = None,
) -> None:
    """
    Background worker:
    1. Fetches last 6 messages from the chat session.
    2. Fetches existing active facts.
    3. Calls extract_facts().
    4. Calls save_facts().
    Safe fail — logs errors, never raises.
    """
    try:
        async with AsyncSessionLocal() as session:
            # Check user consent
            u_uuid = uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id
            user_res = await session.execute(select(User).filter(User.id == u_uuid))
            user = user_res.scalars().first()
            if not user or not user.memory_consent_granted:
                logger.info("Skipping memory extraction: memory consent not granted for user %s", user_id)
                return

            # Fetch last 6 messages scoped to the specific conversation/document
            # so facts never bleed across different documents or patient profiles.
            chat_filters = [Chat.user_id == u_uuid]
            if chat_id:
                try:
                    c_uuid = uuid.UUID(str(chat_id))
                    target_chat = await session.get(Chat, c_uuid)
                    if target_chat is not None:
                        if target_chat.document_id is not None:
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
                messages=chats,
                existing_facts=existing_facts,
                user_id=u_uuid,
                dependent_id=d_uuid,
            )

            stats = await save_facts(
                extraction_result=extraction_result,
                user_id=u_uuid,
                dependent_id=d_uuid,
                source_chat_id=chat_id,
                session=session,
            )
            logger.info("Fact persistence completed for user %s: %s", user_id, stats)

    except Exception as e:
        logger.error("Failed to run background memory extraction: %s", e, exc_info=True)
