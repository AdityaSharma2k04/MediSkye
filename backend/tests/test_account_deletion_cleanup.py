import os
import shutil
import uuid
from pathlib import Path
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from app.core.config import settings


@pytest.mark.anyio
async def test_account_deletion_cleans_faiss_and_bm25():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register a test user
        email = f"delete_user_{uuid.uuid4().hex[:8]}@example.com"
        reg_res = await ac.post("/register", json={
            "email": email,
            "password": "SecurePassword123!",
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200, reg_res.text

        # 2. Login
        login_res = await ac.post("/login", data={
            "username": email,
            "password": "SecurePassword123!",
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Fetch user and create mock document record with physical files
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()
            assert user is not None

            doc_id = uuid.uuid4()
            index_dir = settings.BASE_DIR / "indexes"
            index_dir.mkdir(parents=True, exist_ok=True)

            faiss_dir = index_dir / f"user_{user.id}_doc_{doc_id}.index"
            faiss_dir.mkdir(parents=True, exist_ok=True)
            dummy_index_file = faiss_dir / "index.faiss"
            dummy_index_file.write_text("dummy faiss index data")

            bm25_file = index_dir / f"user_{user.id}_doc_{doc_id}_bm25.pkl"
            bm25_file.write_text("dummy bm25 pickle data")

            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename="test_report.pdf",
                file_path=str(faiss_dir),
            )
            session.add(doc)
            await session.commit()

        # Verify files exist on disk before deletion
        assert faiss_dir.exists()
        assert dummy_index_file.exists()
        assert bm25_file.exists()

        # 4. Delete the account
        del_res = await ac.delete("/users/me", headers=headers)
        assert del_res.status_code == 204

        # 5. Assert BOTH the FAISS directory AND the BM25 pickle are gone
        assert not faiss_dir.exists(), "FAISS directory was not deleted"
        assert not bm25_file.exists(), "BM25 pickle file was orphaned"


@pytest.mark.anyio
async def test_account_deletion_resilient_to_missing_files():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"delete_user_partial_{uuid.uuid4().hex[:8]}@example.com"
        reg_res = await ac.post("/register", json={
            "email": email,
            "password": "SecurePassword123!",
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={
            "username": email,
            "password": "SecurePassword123!",
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            doc_id = uuid.uuid4()
            index_dir = settings.BASE_DIR / "indexes"
            index_dir.mkdir(parents=True, exist_ok=True)

            faiss_dir = index_dir / f"user_{user.id}_doc_{doc_id}.index"
            # Note: Do NOT create faiss_dir (it is missing)
            if faiss_dir.exists():
                shutil.rmtree(faiss_dir)

            # DO create the BM25 pickle file
            bm25_file = index_dir / f"user_{user.id}_doc_{doc_id}_bm25.pkl"
            bm25_file.write_text("orphaned bm25 pickle data")

            doc = Document(
                id=doc_id,
                user_id=user.id,
                filename="test_report_partial.pdf",
                file_path=str(faiss_dir),
            )
            session.add(doc)
            await session.commit()

        assert not faiss_dir.exists()
        assert bm25_file.exists()

        # Deleting account must succeed without FileNotFoundError, and remove the BM25 file
        del_res = await ac.delete("/users/me", headers=headers)
        assert del_res.status_code == 204
        assert not bm25_file.exists(), "BM25 file should be deleted even if FAISS dir is missing"
