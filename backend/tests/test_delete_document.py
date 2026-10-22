import os
import shutil
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat
from app.core.config import settings
from tests.conftest import TEST_PASSWORD


@pytest.mark.anyio
async def test_delete_document_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"delete_doc_{uuid.uuid4().hex[:8]}@example.com"
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
        index_dir = settings.BASE_DIR / "indexes"
        index_dir.mkdir(parents=True, exist_ok=True)

        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            faiss_dir = index_dir / f"user_{user.id}_doc_{doc_id}.index"
            faiss_dir.mkdir(parents=True, exist_ok=True)
            (faiss_dir / "index.faiss").write_text("dummy faiss index")

            bm25_file = index_dir / f"user_{user.id}_doc_{doc_id}_bm25.pkl"
            bm25_file.write_text("dummy bm25 pickle")

            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename="lab_results.pdf",
                file_path=str(faiss_dir),
                title="Lab Results",
            )
            session.add(doc)

            chat = Chat(
                user_id=user.id,
                document_id=doc_id,
                role="user",
                message="Explain my white blood cell count",
            )
            session.add(chat)
            await session.commit()

        assert faiss_dir.exists()
        assert bm25_file.exists()

        # Prime in-memory cache to verify eviction upon deletion
        from app.rag.retriever import cache_hybrid_index, get_cached_hybrid_index
        cache_hybrid_index(str(doc_id), "mock_v", "mock_b")
        cache_hybrid_index(str(faiss_dir), "mock_v", "mock_b")
        assert get_cached_hybrid_index(str(doc_id)) is not None

        # Delete document
        del_res = await ac.delete(f"/users/me/documents/{doc_id}", headers=headers)
        assert del_res.status_code == 204

        # In-memory index cache must be evicted
        assert get_cached_hybrid_index(str(doc_id)) is None
        assert get_cached_hybrid_index(str(faiss_dir)) is None

        # Physical files must be deleted
        assert not faiss_dir.exists()
        assert not bm25_file.exists()

        # DB row must be deleted
        async with AsyncSessionLocal() as session:
            doc_check = await session.execute(select(Document).filter(Document.id == doc_id))
            assert doc_check.scalars().first() is None

            chat_check = await session.execute(select(Chat).filter(Chat.document_id == doc_id))
            assert chat_check.scalars().first() is None

        # Verify GET /users/me/documents is empty
        list_res = await ac.get("/users/me/documents", headers=headers)
        assert list_res.status_code == 200
        assert not any(d["id"] == str(doc_id) for d in list_res.json())


@pytest.mark.anyio
async def test_delete_document_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email1 = f"user1_{uuid.uuid4().hex[:8]}@example.com"
        email2 = f"user2_{uuid.uuid4().hex[:8]}@example.com"

        for em in [email1, email2]:
            await ac.post("/register", json={
                "email": em,
                "password": TEST_PASSWORD,
                "phi_consent_granted": True,
            })

        login1 = await ac.post("/login", data={"username": email1, "password": TEST_PASSWORD})
        login2 = await ac.post("/login", data={"username": email2, "password": TEST_PASSWORD})

        h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}
        h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        doc_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            u1_res = await session.execute(select(User).filter(User.email == email1))
            u1 = u1_res.scalars().first()

            doc = Document(
                id=doc_id,
                user_id=u1.id,
                filename="secret_u1.pdf",
            )
            session.add(doc)
            await session.commit()

        # User 2 tries to delete User 1's document -> 404
        del_attempt = await ac.delete(f"/users/me/documents/{doc_id}", headers=h2)
        assert del_attempt.status_code == 404

        # Invalid UUID -> 400
        bad_uuid_res = await ac.delete("/users/me/documents/not-a-uuid", headers=h1)
        assert bad_uuid_res.status_code == 400
