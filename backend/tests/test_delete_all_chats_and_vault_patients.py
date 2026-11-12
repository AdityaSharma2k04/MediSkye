import uuid
from datetime import datetime, UTC
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.core.auth import get_password_hash
from app.db.models import (
    User,
    Document,
    Chat,
    ChatDocument,
    ChatChunk,
    PatientFact,
    DependentProfile,
    UploadJob,
)
from tests.conftest import TEST_PASSWORD


async def create_user_and_get_headers(ac: AsyncClient, email: str) -> tuple[dict, uuid.UUID]:
    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
            memory_consent_granted=True,
            pre_existing_conditions="Type 2 Diabetes",
            current_medications="Metformin 500mg",
            known_allergies="Penicillin",
            blood_type="O+",
            diet_type="vegetarian",
            activity_level="moderate",
            occupation="Software Engineer",
            height_cm=175.5,
            biological_sex="Male",
        )
        session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.mark.asyncio
async def test_delete_all_chats_full_purge():
    """
    Test 1: Full hard delete of chats, child links (ChatDocument, ChatChunk),
    documents, upload jobs, patient facts, and wiping of clinical profile context.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"purge_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        doc_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        fact_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        upload_job_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            # 1. Create a Document
            doc = Document(
                id=doc_id,
                user_id=user_id,
                filename="blood_panel.pdf",
                file_path=None,
                title="Blood Panel Report",
            )
            session.add(doc)

            # 2. Create an UploadJob
            job = UploadJob(
                id=str(upload_job_id),
                user_id=user_id,
                document_id=str(doc_id),
                status="completed",
            )
            session.add(job)

            # 3. Create a Chat
            chat = Chat(
                id=chat_id,
                user_id=user_id,
                document_id=doc_id,
                session_id=f"doc-{doc_id}",
                role="user",
                message="What is my fasting glucose?",
            )
            session.add(chat)

            # 4. Create ChatDocument link
            chat_doc = ChatDocument(
                chat_id=chat_id,
                document_id=doc_id,
            )
            session.add(chat_doc)

            # 5. Create ChatChunk
            chunk = ChatChunk(
                id=chunk_id,
                chat_id=chat_id,
                user_id=user_id,
                chunk_index=0,
                chunk_text="fasting glucose 110 mg/dL",
            )
            session.add(chunk)

            # 6. Create PatientFact
            fact = PatientFact(
                id=fact_id,
                user_id=user_id,
                fact_type="condition",
                fact_text="Elevated fasting glucose",
                confidence=0.95,
                is_active=True,
                source_type="lab_report",
                source_id=str(doc_id),
            )
            session.add(fact)

            await session.commit()

        # Call DELETE /users/me/chats
        res = await ac.delete("/users/me/chats", headers=headers)
        assert res.status_code in (200, 204)

        # Verify in DB: Chat, ChatDocument, ChatChunk, Document, UploadJob, PatientFact all 0
        async with AsyncSessionLocal() as session:
            chats = (await session.execute(select(Chat).filter(Chat.user_id == user_id))).scalars().all()
            assert len(chats) == 0

            chat_docs = (await session.execute(select(ChatDocument).filter(ChatDocument.chat_id == chat_id))).scalars().all()
            assert len(chat_docs) == 0

            chunks = (await session.execute(select(ChatChunk).filter(ChatChunk.user_id == user_id))).scalars().all()
            assert len(chunks) == 0

            docs = (await session.execute(select(Document).filter(Document.user_id == user_id))).scalars().all()
            assert len(docs) == 0

            jobs = (await session.execute(select(UploadJob).filter(UploadJob.user_id == user_id))).scalars().all()
            assert len(jobs) == 0

            facts = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(facts) == 0

        # Verify profile clinical context wiped via GET /users/me
        me_res = await ac.get("/users/me", headers=headers)
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile.get("pre_existing_conditions") is None
        assert profile.get("current_medications") is None
        assert profile.get("diet_type") is None
        assert profile.get("known_allergies") is None
        assert profile.get("blood_type") is None
        assert profile.get("biological_sex") is None


@pytest.mark.asyncio
async def test_delete_single_chat_session_cascades_facts():
    """
    Test 2: Deleting a session physically deletes the Chat rows and any PatientFact
    whose source_id equals the session_id or chat_id.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"session_del_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        session_id = f"test-session-{uuid.uuid4().hex[:8]}"
        chat_id = uuid.uuid4()
        fact_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            chat = Chat(
                id=chat_id,
                user_id=user_id,
                session_id=session_id,
                role="user",
                message="I have mild asthma.",
            )
            session.add(chat)

            fact = PatientFact(
                id=fact_id,
                user_id=user_id,
                fact_type="condition",
                fact_text="Mild asthma",
                source_type="chat",
                source_id=session_id,
                is_active=True,
            )
            session.add(fact)
            await session.commit()

        # Delete session
        del_res = await ac.delete(f"/users/me/chats/sessions/{session_id}", headers=headers)
        assert del_res.status_code in (200, 204)

        # Assert both Chat and PatientFact are physically deleted
        async with AsyncSessionLocal() as session:
            chats = (await session.execute(select(Chat).filter(Chat.user_id == user_id))).scalars().all()
            assert len(chats) == 0

            facts = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(facts) == 0


@pytest.mark.asyncio
async def test_multi_patient_memory_vault_api_scoping():
    """
    Test 3: Multi-patient memory vault scoping across GET, POST, DELETE.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"multi_vault_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        dep1_id = uuid.uuid4()
        dep2_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            dep1 = DependentProfile(
                id=dep1_id,
                user_id=user_id,
                full_name="Child Alice",
                relationship="daughter",
            )
            dep2 = DependentProfile(
                id=dep2_id,
                user_id=user_id,
                full_name="Parent Bob",
                relationship="father",
            )
            session.add_all([dep1, dep2])

            # Self facts (dependent_id is None)
            f_self1 = PatientFact(
                id=uuid.uuid4(),
                user_id=user_id,
                dependent_id=None,
                fact_type="condition",
                fact_text="Self fact 1: Migraines",
                is_active=True,
            )
            f_self2 = PatientFact(
                id=uuid.uuid4(),
                user_id=user_id,
                dependent_id=None,
                fact_type="allergy",
                fact_text="Self fact 2: Peanut allergy",
                is_active=True,
            )
            # Dep 1 fact
            f_dep1 = PatientFact(
                id=uuid.uuid4(),
                user_id=user_id,
                dependent_id=dep1_id,
                fact_type="condition",
                fact_text="Alice fact: Asthma",
                is_active=True,
            )
            # Dep 2 fact
            f_dep2 = PatientFact(
                id=uuid.uuid4(),
                user_id=user_id,
                dependent_id=dep2_id,
                fact_type="medication",
                fact_text="Bob fact: Lisinopril 10mg",
                is_active=True,
            )
            session.add_all([f_self1, f_self2, f_dep1, f_dep2])
            await session.commit()

        # 1. GET /users/me/memory/facts?patient_id=self -> returns only 2 self facts
        res_self = await ac.get("/users/me/memory/facts?patient_id=self", headers=headers)
        assert res_self.status_code == 200
        self_facts = res_self.json()
        assert len(self_facts) == 2
        assert all("Self fact" in f["fact_text"] for f in self_facts)

        # 2. GET /users/me/memory/facts?patient_id={dep1_id} -> returns only Alice's fact
        res_dep1 = await ac.get(f"/users/me/memory/facts?patient_id={dep1_id}", headers=headers)
        assert res_dep1.status_code == 200
        dep1_facts = res_dep1.json()
        assert len(dep1_facts) == 1
        assert "Alice fact" in dep1_facts[0]["fact_text"]

        # 3. POST /users/me/facts with patient_id={dep2_id} -> creates fact scoped to dep2
        create_res = await ac.post(
            "/users/me/facts",
            headers=headers,
            json={
                "fact_type": "lifestyle",
                "fact_text": "Bob walks 30 minutes daily",
                "patient_id": str(dep2_id),
            },
        )
        assert create_res.status_code == 201
        created_fact = create_res.json()
        assert created_fact["dependent_id"] == str(dep2_id)

        # Verify Bob now has 2 facts
        res_dep2 = await ac.get(f"/users/me/memory/facts?patient_id={dep2_id}", headers=headers)
        assert res_dep2.status_code == 200
        dep2_facts = res_dep2.json()
        assert len(dep2_facts) == 2

        # 4. DELETE /users/me/memory/facts?patient_id={dep1_id} -> clears only Alice's facts
        del_dep1 = await ac.delete(f"/users/me/memory/facts?patient_id={dep1_id}", headers=headers)
        assert del_dep1.status_code in (200, 204)

        # Check Alice has 0 facts now
        res_dep1_after = await ac.get(f"/users/me/memory/facts?patient_id={dep1_id}", headers=headers)
        assert res_dep1_after.status_code == 200
        assert len(res_dep1_after.json()) == 0

        # Check Self still has 2 facts
        res_self_after = await ac.get("/users/me/memory/facts?patient_id=self", headers=headers)
        assert len(res_self_after.json()) == 2

        # Check Bob still has 2 facts
        res_dep2_after = await ac.get(f"/users/me/memory/facts?patient_id={dep2_id}", headers=headers)
        assert len(res_dep2_after.json()) == 2
