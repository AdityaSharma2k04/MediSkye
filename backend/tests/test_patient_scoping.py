import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, DependentProfile
from tests.conftest import TEST_PASSWORD


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


@pytest.mark.asyncio
async def test_query_with_unowned_patient_id_returns_404():
    """Verify POST /query with a patient_id belonging to another user returns HTTP 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email_a = f"owner_{uuid.uuid4().hex[:8]}@test.com"
        email_b = f"intruder_{uuid.uuid4().hex[:8]}@test.com"

        async with AsyncSessionLocal() as s:
            user_a = User(email=email_a, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            user_b = User(email=email_b, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add_all([user_a, user_b])
            await s.commit()
            await s.refresh(user_a)
            await s.refresh(user_b)

            dep_a = DependentProfile(user_id=user_a.id, full_name="Child A", relationship="Child")
            s.add(dep_a)
            await s.commit()
            await s.refresh(dep_a)
            dep_a_id = dep_a.id

        login_b = await ac.post("/login", data={"username": email_b, "password": TEST_PASSWORD})
        assert login_b.status_code == 200
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        res = await ac.post("/query", json={"query": "Hello", "patient_id": str(dep_a_id)}, headers=headers_b)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_query_with_malformed_patient_id_returns_400():
    """Verify POST /query with an invalid patient_id UUID returns HTTP 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        res = await ac.post("/query", json={"query": "Hello", "patient_id": "not-a-valid-uuid"}, headers=headers)
        assert res.status_code == 400
        assert "Invalid patient_id" in res.json()["detail"]


@pytest.mark.asyncio
async def test_query_document_and_patient_mismatch_returns_409():
    """Verify POST /query with a document belonging to dependent A but patient_id for dependent B returns 409."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()
            await s.refresh(user)

            dep_a = DependentProfile(user_id=user.id, full_name="Child A", relationship="Child")
            dep_b = DependentProfile(user_id=user.id, full_name="Child B", relationship="Child")
            s.add_all([dep_a, dep_b])
            await s.commit()
            await s.refresh(dep_a)
            await s.refresh(dep_b)

            doc = Document(user_id=user.id, dependent_id=dep_a.id, filename="report_a.pdf", title="Child A Report")
            s.add(doc)
            await s.commit()
            await s.refresh(doc)
            doc_id = doc.id
            dep_b_id = dep_b.id

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        res = await ac.post("/query", json={"query": "Explain this report", "document_id": str(doc_id), "patient_id": str(dep_b_id)}, headers=headers)
        assert res.status_code == 409
        assert "This report belongs to a different patient profile." in res.json()["detail"]


@pytest.mark.asyncio
async def test_chat_dependent_id_populated_correctly():
    """Verify Chat.dependent_id is populated when patient_id is provided, and None for self."""
    chunk = MagicMock()
    chunk.text = "Hello response"
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk]
    intent_res = MagicMock()
    intent_res.text = "GENERAL_HEALTH"
    mock_client.models.generate_content.return_value = intent_res

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"user_{uuid.uuid4().hex[:8]}@test.com"
            async with AsyncSessionLocal() as s:
                user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
                s.add(user)
                await s.commit()
                await s.refresh(user)

                dep = DependentProfile(user_id=user.id, full_name="Mother", relationship="Mother")
                s.add(dep)
                await s.commit()
                await s.refresh(dep)
                dep_id = dep.id

            login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            session_dep = str(uuid.uuid4())
            res_dep = await ac.post("/query", json={"query": "Hello mother", "patient_id": str(dep_id), "session_id": session_dep}, headers=headers)
            assert res_dep.status_code == 200

            async with AsyncSessionLocal() as s:
                result = await s.execute(select(Chat).where(Chat.session_id == session_dep))
                chats = result.scalars().all()
                assert len(chats) > 0
                for c in chats:
                    assert c.dependent_id == dep_id

            session_self = str(uuid.uuid4())
            res_self = await ac.post("/query", json={"query": "Hello self", "patient_id": "self", "session_id": session_self}, headers=headers)
            assert res_self.status_code == 200

            async with AsyncSessionLocal() as s:
                result = await s.execute(select(Chat).where(Chat.session_id == session_self))
                chats_self = result.scalars().all()
                assert len(chats_self) > 0
                for c in chats_self:
                    assert c.dependent_id is None
