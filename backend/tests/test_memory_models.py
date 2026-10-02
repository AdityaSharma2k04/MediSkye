import uuid
import pytest
from datetime import datetime, date
from sqlalchemy import text
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, PatientFact, ChatChunk, ChatDocument, Chat, Document
from app.core.auth import get_password_hash


@pytest.mark.asyncio
async def test_personalization_fields_save_and_retrieve():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"pers_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            height_cm=175.5,
            diet_type="vegetarian",
            activity_level="moderate",
            occupation="Software Engineer",
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        assert user.height_cm == 175.5
        assert user.diet_type == "vegetarian"
        assert user.activity_level == "moderate"
        assert user.occupation == "Software Engineer"
        assert user.memory_consent_granted is True

        # Test dependent personalization fields
        dep = DependentProfile(
            user_id=user.id,
            relationship="Child",
            full_name="Baby Doe",
            height_cm=110.0,
            diet_type="vegan",
            activity_level="active",
            occupation="Student",
        )
        session.add(dep)
        await session.commit()
        await session.refresh(dep)

        assert dep.height_cm == 110.0
        assert dep.diet_type == "vegan"
        assert dep.activity_level == "active"
        assert dep.occupation == "Student"


@pytest.mark.asyncio
async def test_create_user_and_facts_query_by_type():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"facts_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        facts_data = [
            ("condition", "Type 2 Diabetes"),
            ("medication", "Metformin 500mg"),
            ("allergy", "Penicillin"),
            ("lifestyle", "Vegetarian diet, runs 3x/week"),
            ("measurement", "HbA1c: 7.2%"),
        ]

        for f_type, f_text in facts_data:
            fact = PatientFact(
                user_id=user.id,
                fact_type=f_type,
                fact_text=f_text,
                confidence=0.95,
                source_type="chat",
            )
            session.add(fact)
        await session.commit()

        # Query by fact_type
        res = await session.execute(
            select(PatientFact).filter(
                PatientFact.user_id == user.id,
                PatientFact.fact_type == "medication",
            )
        )
        meds = res.scalars().all()
        assert len(meds) == 1
        assert meds[0].fact_text == "Metformin 500mg"


@pytest.mark.asyncio
async def test_encrypted_string_raw_sql_vs_orm():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"enc_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        secret_fact_text = "Severe peanut anaphylaxis requires EpiPen"
        fact = PatientFact(
            user_id=user.id,
            fact_type="allergy",
            fact_text=secret_fact_text,
            source_type="chat",
        )
        session.add(fact)
        await session.commit()
        await session.refresh(fact)

        # ORM access shows plaintext
        assert fact.fact_text == secret_fact_text

        # Raw SQL query shows ciphertext (does NOT contain the raw plaintext secret)
        raw_res = await session.execute(
            text("SELECT fact_text FROM patient_facts WHERE id = :fid OR id = :fid_hex"),
            {"fid": str(fact.id), "fid_hex": fact.id.hex},
        )
        raw_row = raw_res.first()
        assert raw_row is not None
        raw_ciphertext = raw_row[0]
        assert secret_fact_text not in raw_ciphertext
        assert isinstance(raw_ciphertext, str)


@pytest.mark.asyncio
async def test_dependent_scoped_facts_dont_leak():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"leak_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        dep1 = DependentProfile(
            user_id=user.id,
            relationship="Child",
            full_name="Child One",
        )
        dep2 = DependentProfile(
            user_id=user.id,
            relationship="Spouse",
            full_name="Spouse One",
        )
        session.add_all([dep1, dep2])
        await session.commit()
        await session.refresh(dep1)
        await session.refresh(dep2)

        # Fact for User (Self)
        user_fact = PatientFact(
            user_id=user.id,
            dependent_id=None,
            fact_type="condition",
            fact_text="Adult Hypertension",
            source_type="chat",
        )
        # Fact for Child (Dep 1)
        dep1_fact = PatientFact(
            user_id=user.id,
            dependent_id=dep1.id,
            fact_type="condition",
            fact_text="Childhood Asthma",
            source_type="chat",
        )
        session.add_all([user_fact, dep1_fact])
        await session.commit()

        # Query for Self (dependent_id is None)
        self_res = await session.execute(
            select(PatientFact).filter(
                PatientFact.user_id == user.id,
                PatientFact.dependent_id.is_(None),
            )
        )
        self_facts = self_res.scalars().all()
        assert len(self_facts) == 1
        assert self_facts[0].fact_text == "Adult Hypertension"

        # Query for Dep 1
        dep1_res = await session.execute(
            select(PatientFact).filter(
                PatientFact.user_id == user.id,
                PatientFact.dependent_id == dep1.id,
            )
        )
        d1_facts = dep1_res.scalars().all()
        assert len(d1_facts) == 1
        assert d1_facts[0].fact_text == "Childhood Asthma"

        # Query for Dep 2 (no facts assigned)
        dep2_res = await session.execute(
            select(PatientFact).filter(
                PatientFact.user_id == user.id,
                PatientFact.dependent_id == dep2.id,
            )
        )
        d2_facts = dep2_res.scalars().all()
        assert len(d2_facts) == 0


@pytest.mark.asyncio
async def test_chat_document_bidirectional_join():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"chatdoc_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc1 = Document(user_id=user.id, filename="cbc_report.pdf")
        doc2 = Document(user_id=user.id, filename="lipid_panel.pdf")
        session.add_all([doc1, doc2])
        await session.commit()
        await session.refresh(doc1)
        await session.refresh(doc2)

        chat = Chat(user_id=user.id, message="Compare my results", role="user")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        # Attach doc1 and doc2 to chat
        cd1 = ChatDocument(chat_id=chat.id, document_id=doc1.id)
        cd2 = ChatDocument(chat_id=chat.id, document_id=doc2.id)
        session.add_all([cd1, cd2])
        await session.commit()

        # Query docs for chat
        res = await session.execute(
            select(ChatDocument).filter(ChatDocument.chat_id == chat.id)
        )
        linked_docs = res.scalars().all()
        assert len(linked_docs) == 2
        doc_ids = {ld.document_id for ld in linked_docs}
        assert doc1.id in doc_ids
        assert doc2.id in doc_ids

        # Query chats for doc1
        res_doc = await session.execute(
            select(ChatDocument).filter(ChatDocument.document_id == doc1.id)
        )
        linked_chats = res_doc.scalars().all()
        assert len(linked_chats) == 1
        assert linked_chats[0].chat_id == chat.id


@pytest.mark.asyncio
async def test_cascade_delete_chat_deletes_chunks_and_chat_documents():
    async with AsyncSessionLocal() as session:
        user = User(
            email=f"cascade_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("Password123!"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(user_id=user.id, filename="test.pdf")
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

        chat = Chat(user_id=user.id, message="What is my glucose?", role="user")
        session.add(chat)
        await session.commit()
        await session.refresh(chat)

        cd = ChatDocument(chat_id=chat.id, document_id=doc.id)
        chunk = ChatChunk(
            user_id=user.id,
            chat_id=chat.id,
            chunk_text="User asked about glucose",
            chunk_index=0,
            embedding=[0.1, 0.2, 0.3],
        )
        session.add_all([cd, chunk])
        await session.commit()

        # Verify they exist
        res_cd = await session.execute(select(ChatDocument).filter(ChatDocument.chat_id == chat.id))
        assert len(res_cd.scalars().all()) == 1

        res_chunk = await session.execute(select(ChatChunk).filter(ChatChunk.chat_id == chat.id))
        assert len(res_chunk.scalars().all()) == 1

        # Delete chat
        await session.delete(chat)
        await session.commit()

        # Verify cascade deletion
        res_cd_after = await session.execute(select(ChatDocument).filter(ChatDocument.chat_id == chat.id))
        assert len(res_cd_after.scalars().all()) == 0

        res_chunk_after = await session.execute(select(ChatChunk).filter(ChatChunk.chat_id == chat.id))
        assert len(res_chunk_after.scalars().all()) == 0
