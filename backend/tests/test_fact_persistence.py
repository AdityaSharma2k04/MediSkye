import uuid
import pytest
from unittest.mock import patch
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, PatientFact, Chat
from app.core.auth import get_password_hash
from app.services.fact_persistence import save_facts, process_chat_memory_extraction


@pytest.mark.asyncio
async def test_save_facts_and_retraction_e2e():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"persist_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 1. Insert first fact
        res1 = await save_facts(
            extraction_result={
                "facts": [
                    {"type": "condition", "text": "Hypertension", "confidence": 1.0, "excerpt": "I have hypertension"},
                    {"type": "medication", "text": "Lisinopril 10mg", "confidence": 0.9}
                ],
                "retractions": [],
            },
            user_id=user.id,
            dependent_id=None,
            source_chat_id=None,
            session=session,
        )
        assert res1["inserted"] == 2
        assert res1["updated"] == 0

        # Verify rows exist in DB
        facts_res = await session.execute(
            select(PatientFact).filter(PatientFact.user_id == user.id, PatientFact.is_active.is_(True))
        )
        facts = facts_res.scalars().all()
        assert len(facts) == 2
        lisinopril_fact = next(f for f in facts if f.fact_text == "Lisinopril 10mg")

        # 2. Duplicate fact should update last_seen_at without creating a new row
        first_last_seen = lisinopril_fact.last_seen_at
        res2 = await save_facts(
            extraction_result={
                "facts": [
                    {"type": "medication", "text": "Lisinopril 10mg", "confidence": 0.95}
                ],
                "retractions": [],
            },
            user_id=user.id,
            dependent_id=None,
            source_chat_id=None,
            session=session,
        )
        assert res2["inserted"] == 0
        assert res2["updated"] == 1

        await session.refresh(lisinopril_fact)
        assert lisinopril_fact.confidence == 0.95

        # 3. Retract medication
        res3 = await save_facts(
            extraction_result={
                "facts": [],
                "retractions": [
                    {"existing_fact_id": str(lisinopril_fact.id), "reason": "Patient stopped lisinopril"}
                ]
            },
            user_id=user.id,
            dependent_id=None,
            source_chat_id=None,
            session=session,
        )
        assert res3["retracted"] == 1

        # Verify row still exists in DB but is_active is False
        await session.refresh(lisinopril_fact)
        assert lisinopril_fact.is_active is False


@pytest.mark.asyncio
async def test_process_chat_memory_extraction_consent_gate():
    async with AsyncSessionLocal() as session:
        user_no_consent = User(
            email=f"noconsent_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=False,
        )
        session.add(user_no_consent)
        await session.commit()
        await session.refresh(user_no_consent)

        chat = Chat(user_id=user_no_consent.id, role="user", message="I have asthma.")
        session.add(chat)
        await session.commit()

    with patch("app.services.fact_persistence.extract_facts") as mock_extract:
        # Run background worker for user without consent
        await process_chat_memory_extraction(
            chat_id=None,
            user_id=user_no_consent.id,
            dependent_id=None,
        )
        # extract_facts should NOT be called
        mock_extract.assert_not_called()
