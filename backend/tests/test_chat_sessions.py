import uuid
import pytest
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, PatientFact
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
        )
        session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.mark.asyncio
async def test_multi_session_standalone_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"session_iso_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        async with AsyncSessionLocal() as session:
            session.add_all([
                Chat(
                    user_id=user_id,
                    session_id="session-alpha",
                    session_title="Alpha Medical Discussion",
                    role="user",
                    message="What is normal resting heart rate?",
                ),
                Chat(
                    user_id=user_id,
                    session_id="session-alpha",
                    session_title="Alpha Medical Discussion",
                    role="assistant",
                    message="Normal resting heart rate for adults is 60-100 bpm.",
                ),
                Chat(
                    user_id=user_id,
                    session_id="session-beta",
                    session_title="Beta Diet Questions",
                    role="user",
                    message="Can I eat grapefruit with statins?",
                ),
                Chat(
                    user_id=user_id,
                    session_id="session-beta",
                    session_title="Beta Diet Questions",
                    role="assistant",
                    message="Grapefruit interacts with certain statins like atorvastatin.",
                ),
            ])
            await session.commit()

        # 1. Fetch without filter -> returns all 4 messages
        res_all = await ac.get("/users/me/chats", headers=headers)
        assert res_all.status_code == 200
        all_chats = res_all.json()
        assert len(all_chats) == 4
        sessions_found = {c["session_id"] for c in all_chats}
        assert sessions_found == {"session-alpha", "session-beta"}

        # 2. Filter by session-alpha -> returns only 2 messages
        res_alpha = await ac.get("/users/me/chats?session_id=session-alpha", headers=headers)
        assert res_alpha.status_code == 200
        alpha_chats = res_alpha.json()
        assert len(alpha_chats) == 2
        for c in alpha_chats:
            assert c["session_id"] == "session-alpha"
            assert c["session_title"] == "Alpha Medical Discussion"

        # 3. Filter by session-beta -> returns only 2 messages
        res_beta = await ac.get("/users/me/chats?session_id=session-beta", headers=headers)
        assert res_beta.status_code == 200
        beta_chats = res_beta.json()
        assert len(beta_chats) == 2
        for c in beta_chats:
            assert c["session_id"] == "session-beta"
            assert c["session_title"] == "Beta Diet Questions"


@pytest.mark.asyncio
async def test_rename_chat_session_and_idor_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email1 = f"rename_user1_{uuid.uuid4().hex[:8]}@test.com"
        headers1, user1_id = await create_user_and_get_headers(ac, email1)

        email2 = f"rename_user2_{uuid.uuid4().hex[:8]}@test.com"
        headers2, _ = await create_user_and_get_headers(ac, email2)

        async with AsyncSessionLocal() as session:
            session.add(
                Chat(
                    user_id=user1_id,
                    session_id="user1-session-1",
                    session_title="Old Title",
                    role="user",
                    message="Hello doctor",
                )
            )
            await session.commit()

        # User 2 tries to rename User 1's session -> 404
        idor_res = await ac.patch(
            "/users/me/chats/sessions/user1-session-1",
            json={"title": "Hacked Title"},
            headers=headers2,
        )
        assert idor_res.status_code == 404

        # User 1 renames their own session -> 200
        rename_res = await ac.patch(
            "/users/me/chats/sessions/user1-session-1",
            json={"title": "Brand New Consultation"},
            headers=headers1,
        )
        assert rename_res.status_code == 200
        data = rename_res.json()
        assert data["session_id"] == "user1-session-1"
        assert data["session_title"] == "Brand New Consultation"

        # Verify persisted via GET
        get_res = await ac.get("/users/me/chats?session_id=user1-session-1", headers=headers1)
        assert get_res.status_code == 200
        chats = get_res.json()
        assert len(chats) == 1
        assert chats[0]["session_title"] == "Brand New Consultation"


@pytest.mark.asyncio
async def test_delete_chat_session_cascades_facts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"del_sess_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        chat_turn_id = uuid.uuid4()
        other_turn_id = uuid.uuid4()
        fact_to_delete_id = uuid.uuid4()
        fact_to_keep_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            # Session to delete
            session.add(
                Chat(
                    id=chat_turn_id,
                    user_id=user_id,
                    session_id="target-session",
                    session_title="Target Session",
                    role="user",
                    message="I have severe migraines since yesterday",
                )
            )
            # Associated fact from this chat turn
            session.add(
                PatientFact(
                    id=fact_to_delete_id,
                    user_id=user_id,
                    fact_type="symptom",
                    fact_text="Severe migraines",
                    source_type="chat",
                    source_id=str(chat_turn_id),
                    is_active=True,
                )
            )

            # Another session to keep
            session.add(
                Chat(
                    id=other_turn_id,
                    user_id=user_id,
                    session_id="keep-session",
                    session_title="Keep Session",
                    role="user",
                    message="I take 500mg Metformin",
                )
            )
            session.add(
                PatientFact(
                    id=fact_to_keep_id,
                    user_id=user_id,
                    fact_type="medication",
                    fact_text="Metformin 500mg",
                    source_type="chat",
                    source_id=str(other_turn_id),
                    is_active=True,
                )
            )
            await session.commit()

        # Delete target-session
        del_res = await ac.delete("/users/me/chats/sessions/target-session", headers=headers)
        assert del_res.status_code == 204

        # Direct DB verification: target chat and fact physically removed
        async with AsyncSessionLocal() as session:
            c_check = await session.execute(select(Chat).filter(Chat.session_id == "target-session"))
            assert c_check.scalars().first() is None

            f_deleted = await session.execute(
                select(PatientFact).filter(PatientFact.id == fact_to_delete_id)
            )
            assert f_deleted.scalars().first() is None  # Physically deleted

            # Keep session and its fact still exist
            c_keep = await session.execute(select(Chat).filter(Chat.session_id == "keep-session"))
            assert c_keep.scalars().first() is not None

            f_keep = await session.execute(
                select(PatientFact).filter(PatientFact.id == fact_to_keep_id)
            )
            assert f_keep.scalars().first() is not None


@pytest.mark.asyncio
async def test_clear_all_chats_cascades_facts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"clear_all_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        chat_id_1 = uuid.uuid4()
        chat_id_2 = uuid.uuid4()
        fact_id_1 = uuid.uuid4()
        fact_id_2 = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            session.add_all([
                Chat(
                    id=chat_id_1,
                    user_id=user_id,
                    session_id="sess-1",
                    role="user",
                    message="Standalone chat 1",
                ),
                Chat(
                    id=chat_id_2,
                    user_id=user_id,
                    session_id="sess-2",
                    role="user",
                    message="Standalone chat 2",
                ),
                PatientFact(
                    id=fact_id_1,
                    user_id=user_id,
                    fact_type="symptom",
                    fact_text="Fact 1",
                    source_type="chat",
                    source_id=str(chat_id_1),
                    is_active=True,
                ),
                PatientFact(
                    id=fact_id_2,
                    user_id=user_id,
                    fact_type="symptom",
                    fact_text="Fact 2",
                    source_type="chat",
                    source_id=str(chat_id_2),
                    is_active=True,
                ),
            ])
            await session.commit()

        # Clear all standalone chats
        clear_res = await ac.delete("/users/me/chats", headers=headers)
        assert clear_res.status_code == 204

        # Verify in DB: 0 chats and 0 facts
        async with AsyncSessionLocal() as session:
            chats = (await session.execute(select(Chat).filter(Chat.user_id == user_id))).scalars().all()
            assert len(chats) == 0

            facts = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(facts) == 0


@pytest.mark.asyncio
async def test_delete_document_cascades_chat_and_facts():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"doc_cascade_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        doc_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        chat_fact_id = uuid.uuid4()
        doc_fact_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            session.add(
                Document(
                    id=doc_id,
                    user_id=user_id,
                    filename="metabolic_panel.pdf",
                    file_path="/tmp/test_panel.pdf",
                    title="Metabolic Panel",
                )
            )
            session.add(
                Chat(
                    id=chat_id,
                    user_id=user_id,
                    document_id=doc_id,
                    session_id=f"doc-{doc_id}",
                    role="user",
                    message="Explain high potassium",
                )
            )
            session.add(
                PatientFact(
                    id=chat_fact_id,
                    user_id=user_id,
                    fact_type="lab_result",
                    fact_text="Potassium 5.4 mmol/L",
                    source_type="chat",
                    source_id=str(chat_id),
                    is_active=True,
                )
            )
            session.add(
                PatientFact(
                    id=doc_fact_id,
                    user_id=user_id,
                    fact_type="lab_result",
                    fact_text="Creatinine 1.2 mg/dL",
                    source_type="document",
                    source_id=str(doc_id),
                    is_active=True,
                )
            )
            await session.commit()

        # Delete document
        del_res = await ac.delete(f"/users/me/documents/{doc_id}", headers=headers)
        assert del_res.status_code == 204

        # Verify DB: Document, Chat, and BOTH facts are physically deleted
        async with AsyncSessionLocal() as session:
            doc_check = await session.execute(select(Document).filter(Document.id == doc_id))
            assert doc_check.scalars().first() is None

            chat_check = await session.execute(select(Chat).filter(Chat.document_id == doc_id))
            assert chat_check.scalars().first() is None

            cf_check = await session.execute(select(PatientFact).filter(PatientFact.id == chat_fact_id))
            assert cf_check.scalars().first() is None

            df_check = await session.execute(select(PatientFact).filter(PatientFact.id == doc_fact_id))
            assert df_check.scalars().first() is None


@pytest.mark.asyncio
async def test_hard_delete_facts_physical_erasure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"fact_hard_del_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        fact1_id = uuid.uuid4()
        fact2_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            session.add_all([
                PatientFact(
                    id=fact1_id,
                    user_id=user_id,
                    fact_type="allergy",
                    fact_text="Penicillin allergy",
                    source_type="user_edit",
                    is_active=True,
                ),
                PatientFact(
                    id=fact2_id,
                    user_id=user_id,
                    fact_type="condition",
                    fact_text="Asthma",
                    source_type="user_edit",
                    is_active=True,
                ),
            ])
            await session.commit()

        # 1. Hard delete single fact
        del_single = await ac.delete(f"/users/me/memory/facts/{fact1_id}", headers=headers)
        assert del_single.status_code == 200

        async with AsyncSessionLocal() as session:
            f1 = (await session.execute(select(PatientFact).filter(PatientFact.id == fact1_id))).scalars().first()
            assert f1 is None  # Physically erased

            f2 = (await session.execute(select(PatientFact).filter(PatientFact.id == fact2_id))).scalars().first()
            assert f2 is not None

        # 2. Hard clear all facts
        del_all = await ac.delete("/users/me/memory/facts", headers=headers)
        assert del_all.status_code == 200
        assert del_all.json()["count"] == 1

        async with AsyncSessionLocal() as session:
            remaining = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(remaining) == 0


@pytest.mark.asyncio
async def test_revoke_consent_with_clear_existing():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"revoke_clear_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_get_headers(ac, email)

        fact_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            session.add(
                PatientFact(
                    id=fact_id,
                    user_id=user_id,
                    fact_type="condition",
                    fact_text="Hypertension",
                    source_type="chat",
                    is_active=True,
                )
            )
            await session.commit()

        # Revoke consent with clear_existing=True
        revoke_res = await ac.post(
            "/users/me/memory/consent",
            json={"consent": False, "clear_existing": True},
            headers=headers,
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["memory_consent_granted"] is False

        # Direct DB verification: user consent is false AND fact is physically deleted
        async with AsyncSessionLocal() as session:
            u = (await session.execute(select(User).filter(User.id == user_id))).scalars().first()
            assert u.memory_consent_granted is False

            f = (await session.execute(select(PatientFact).filter(PatientFact.id == fact_id))).scalars().first()
            assert f is None
