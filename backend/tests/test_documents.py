import uuid
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat
from app.core.security import clean_filename_to_title, generate_title_from_query
from tests.conftest import TEST_PASSWORD


EMBED_DIM = 768


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text):
        return [0.1] * EMBED_DIM

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


def test_clean_filename_heuristics():
    assert clean_filename_to_title("cbc_blood_test_report_2026.pdf") == "Cbc"
    assert clean_filename_to_title("cardiology_consultation.pdf") == "Cardiology Consultation"
    assert clean_filename_to_title("report.pdf") == "Report"
    assert clean_filename_to_title("") == "New Conversation"


def test_generate_title_from_query():
    assert generate_title_from_query("What is my cholesterol level?") == "What is my cholesterol level?"
    assert generate_title_from_query("What are my blood sugar results from yesterday morning?") == "What are my blood sugar"
    assert generate_title_from_query("Hello") == "Hello"
    assert generate_title_from_query("") == "New Conversation"


@pytest.mark.anyio
async def test_document_title_persistence_and_update():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"doc_title_{uuid.uuid4().hex[:8]}@example.com"
        reg_res = await ac.post("/register", json={
            "email": email,
            "password": TEST_PASSWORD,
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={
            "username": email,
            "password": TEST_PASSWORD,
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        doc_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename="cardiology_checkup.pdf",
                title=clean_filename_to_title("cardiology_checkup.pdf"),
            )
            session.add(doc)
            await session.commit()

        # 1. Fetch document list via GET /users/me/documents
        list_res = await ac.get("/users/me/documents", headers=headers)
        assert list_res.status_code == 200
        docs = list_res.json()
        target_doc = next(d for d in docs if d["id"] == str(doc_id))
        assert target_doc["title"] == "Cardiology Checkup"

        # 2. Update title via PATCH /users/me/documents/{id}/title
        patch_res = await ac.patch(
            f"/users/me/documents/{doc_id}/title",
            json={"title": "Renamed Heart Report"},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json() == {"id": str(doc_id), "title": "Renamed Heart Report"}

        # 3. Verify title persisted in Neon DB by calling GET /users/me/documents
        list_res_2 = await ac.get("/users/me/documents", headers=headers)
        assert list_res_2.status_code == 200
        docs_2 = list_res_2.json()
        target_doc_2 = next(d for d in docs_2 if d["id"] == str(doc_id))
        assert target_doc_2["title"] == "Renamed Heart Report"

        # 4. Verify PATCH /documents/{id}/title route compatibility
        patch_res_2 = await ac.patch(
            f"/documents/{doc_id}/title",
            json={"title": "Updated via Legacy Route"},
            headers=headers,
        )
        assert patch_res_2.status_code == 200
        assert patch_res_2.json() == {"id": str(doc_id), "title": "Updated via Legacy Route"}

        # 5. Verify persistence again
        list_res_3 = await ac.get("/users/me/documents", headers=headers)
        assert list_res_3.status_code == 200
        docs_3 = list_res_3.json()
        target_doc_3 = next(d for d in docs_3 if d["id"] == str(doc_id))
        assert target_doc_3["title"] == "Updated via Legacy Route"


@pytest.mark.anyio
async def test_document_auto_naming_on_first_query():
    transport = ASGITransport(app=app)

    chunk1 = MagicMock()
    chunk1.text = "Your results are normal."
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk1]
    intent_response = MagicMock()
    intent_response.text = "CASUAL"
    mock_client.models.generate_content.return_value = intent_response

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"query_title_{uuid.uuid4().hex[:8]}@example.com"
        await ac.post("/register", json={
            "email": email,
            "password": TEST_PASSWORD,
            "phi_consent_granted": True,
        })
        login_res = await ac.post("/login", data={
            "username": email,
            "password": TEST_PASSWORD,
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        doc_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            # Seed a document with default title
            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename="blood_test.pdf",
                title="New Conversation",
            )
            session.add(doc)
            await session.commit()

        with (
            patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
            patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
            patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
            patch("google.genai.Client", return_value=mock_client),
        ):
            query_res = await ac.post(
                "/query",
                json={
                    "session_id": str(doc_id),
                    "query": "What are my blood sugar levels today and why?",
                },
                headers=headers,
            )
            assert query_res.status_code == 200
            stream_body = query_res.text

            # Stream emitted title event
            expected_title = "What are my blood sugar"
            assert expected_title in stream_body

        # Verify DB persisted title
        docs_res = await ac.get("/users/me/documents", headers=headers)
        assert docs_res.status_code == 200
        docs = docs_res.json()
        target = next(d for d in docs if d["id"] == str(doc_id))
        assert target["title"] == expected_title


@pytest.mark.anyio
async def test_document_rename_idor_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create User A with Doc A
        user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
        await ac.post("/register", json={"email": user_a_email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        login_a = await ac.post("/login", data={"username": user_a_email, "password": TEST_PASSWORD})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        doc_a_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            u_res = await session.execute(select(User).filter(User.email == user_a_email))
            user_a = u_res.scalars().first()
            doc_a = Document(id=doc_a_id, user_id=user_a.id, filename="doc_a.pdf", title="User A Doc")
            session.add(doc_a)
            await session.commit()

        # Create User B
        user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"
        await ac.post("/register", json={"email": user_b_email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        login_b = await ac.post("/login", data={"username": user_b_email, "password": TEST_PASSWORD})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # User B attempts to rename User A's document via /users/me/documents/{id}/title
        res = await ac.patch(
            f"/users/me/documents/{doc_a_id}/title",
            json={"title": "Hacked Title"},
            headers=headers_b,
        )
        assert res.status_code == 404

        # User B attempts to rename User A's document via /documents/{id}/title
        res_legacy = await ac.patch(
            f"/documents/{doc_a_id}/title",
            json={"title": "Hacked Title Legacy"},
            headers=headers_b,
        )
        assert res_legacy.status_code == 404

        # Verify Doc A title remains untouched
        list_res = await ac.get("/users/me/documents", headers=headers_a)
        docs_a = list_res.json()
        assert docs_a[0]["title"] == "User A Doc"
