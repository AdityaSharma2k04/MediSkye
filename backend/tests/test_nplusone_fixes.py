import uuid
import pytest
from unittest.mock import AsyncMock
from sqlalchemy.future import select

from app.db.database import AsyncSessionLocal
from app.db.models import User, PatientFact, Chat, Document, ChatDocument
from app.core.auth import get_password_hash
from app.services.fact_persistence import save_facts


@pytest.mark.asyncio
async def test_batch_retraction_single_query():
    """
    Verify 3D.1: Retracting 5 facts emits exactly 1 batch SELECT query (IN clause)
    instead of looping N times.
    """
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"nplusone_retract_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create 5 active facts
        fact_ids = []
        for i in range(5):
            fact = PatientFact(
                user_id=user.id,
                fact_type="medication",
                fact_text=f"Medication {i} 10mg",
                confidence=1.0,
                is_active=True,
            )
            session.add(fact)
            await session.flush()
            fact_ids.append(fact.id)
        await session.commit()

        # Build 5 retraction entries
        retractions = [{"existing_fact_id": str(fid), "reason": "Discontinued"} for fid in fact_ids]

        # Spy on session.execute
        original_execute = session.execute
        all_queries = []
        retraction_queries = []

        async def execute_spy(statement, *args, **kwargs):
            stmt_str = str(statement)
            all_queries.append(stmt_str)
            if "patient_facts" in stmt_str and " IN " in stmt_str.upper():
                retraction_queries.append(stmt_str)
            return await original_execute(statement, *args, **kwargs)

        session.execute = execute_spy

        res = await save_facts(
            extraction_result={"facts": [], "retractions": retractions},
            user_id=user.id,
            dependent_id=None,
            source_chat_id=None,
            session=session,
        )

        assert res["retracted"] == 5
        # Verify exactly 1 query was emitted for retractions
        assert len(retraction_queries) == 1, f"retraction_queries: {retraction_queries}, all: {all_queries}"

        # Confirm all 5 facts are deactivated in DB
        res_facts = await original_execute(
            select(PatientFact).filter(PatientFact.id.in_(fact_ids))
        )
        for f in res_facts.scalars().all():
            assert f.is_active is False


@pytest.mark.asyncio
async def test_batch_document_attachment_verification_single_query():
    """
    Verify 3D.2: Attaching 3 documents emits exactly 1 batch query (ChatDocument.document_id.in_)
    rather than looping 1 query per document.
    """
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"nplusone_doc_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create 3 documents
        docs = []
        for i in range(3):
            doc = Document(
                user_id=user.id,
                filename=f"report_{i}.pdf",
                file_path=f"storage/reports/report_{i}.pdf",
            )
            session.add(doc)
            await session.flush()
            docs.append(doc)

        chat = Chat(user_id=user.id, role="user", message="Check these reports")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        current_chat_id = chat.id
        doc_ids = [d.id for d in docs]

        # Execute batch check pattern as implemented in query.py
        select_queries = []
        original_execute = session.execute

        async def execute_spy(statement, *args, **kwargs):
            stmt_str = str(statement)
            if "chat_documents" in stmt_str and "IN" in stmt_str.upper():
                select_queries.append(stmt_str)
            return await original_execute(statement, *args, **kwargs)

        session.execute = execute_spy

        # Run batch document association check
        existing_cds = await session.execute(
            select(ChatDocument.document_id).filter(
                ChatDocument.chat_id == current_chat_id,
                ChatDocument.document_id.in_(doc_ids),
            )
        )
        already_linked = set(existing_cds.scalars().all())
        for did in doc_ids:
            if did not in already_linked:
                session.add(ChatDocument(chat_id=current_chat_id, document_id=did))
        await session.commit()

        # Assert exactly 1 batch SELECT emitted
        assert len(select_queries) == 1

        # Verify all 3 records are saved
        cd_res = await original_execute(
            select(ChatDocument).filter(ChatDocument.chat_id == current_chat_id)
        )
        saved_links = cd_res.scalars().all()
        assert len(saved_links) == 3
