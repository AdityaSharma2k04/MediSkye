import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document as LCDocument
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_metrics_persistent_caching_and_force_refresh():
    email = f"metrics_cache_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="lab_report.pdf",
            file_path="dummy/path/doc.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '[{"test": "Hemoglobin", "value": "15.0", "unit": "g/dL", "range": "13.8 - 17.2", "status": "Normal"}]'
    )
    mock_client.models.generate_content.return_value = mock_response

    mock_docs = [LCDocument(page_content="Hemoglobin: 15.0 g/dL (ref 13.8 - 17.2) Normal", metadata={})]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.metrics.FAISS.load_local", return_value=MagicMock()),
        patch("app.api.v1.endpoints.metrics.retrieve_relevant_docs", return_value=mock_docs),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}", "X-Session-ID": str(doc_id)}

            # 1st call: Cache miss -> invokes Gemini
            res1 = await ac.post("/extract-metrics", headers=headers)
            assert res1.status_code == 200
            data1 = res1.json()
            assert len(data1["metrics"]) == 1
            assert data1["metrics"][0]["test"] == "Hemoglobin"
            assert mock_client.models.generate_content.call_count == 1

            # 2nd call: Cache hit -> does NOT invoke Gemini again
            res2 = await ac.post("/extract-metrics", headers=headers)
            assert res2.status_code == 200
            data2 = res2.json()
            assert len(data2["metrics"]) == 1
            assert data2["metrics"][0]["test"] == "Hemoglobin"
            assert mock_client.models.generate_content.call_count == 1

            # Also verify GET /users/me/documents/{id}/metrics route returns the cached metrics
            res_get = await ac.get(f"/users/me/documents/{doc_id}/metrics", headers={"Authorization": f"Bearer {token}"})
            assert res_get.status_code == 200
            assert len(res_get.json()["metrics"]) == 1
            assert mock_client.models.generate_content.call_count == 1

            # 3rd call with force_refresh=true: Re-invokes Gemini
            res3 = await ac.post("/extract-metrics?force_refresh=true", headers=headers)
            assert res3.status_code == 200
            assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_metrics_empty_list_is_cached():
    """Verify that an imaging report returning [] is cached and does NOT re-trigger Gemini."""
    email = f"metrics_empty_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="xray_chest.pdf",
            file_path="dummy/path/doc.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '[]'
    mock_client.models.generate_content.return_value = mock_response

    mock_docs = [LCDocument(page_content="Chest X-Ray normal lungs no infiltration", metadata={})]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.metrics.FAISS.load_local", return_value=MagicMock()),
        patch("app.api.v1.endpoints.metrics.retrieve_relevant_docs", return_value=mock_docs),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}", "X-Session-ID": str(doc_id)}

            # 1st call -> LLM returns []
            res1 = await ac.post("/extract-metrics", headers=headers)
            assert res1.status_code == 200
            assert res1.json()["metrics"] == []
            assert mock_client.models.generate_content.call_count == 1

            # 2nd call -> Returns cached [] without LLM invocation
            res2 = await ac.post("/extract-metrics", headers=headers)
            assert res2.status_code == 200
            assert res2.json()["metrics"] == []
            assert mock_client.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_summary_persistent_caching_and_emoji_stripping():
    email = f"summary_cache_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="blood_work.pdf",
            file_path="dummy/path/doc.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "## Clinical Summary 🩺\n\n"
        "### Overview 📋\n"
        "Patient shows mild anemia. 🩸\n\n"
        "### Next Steps\n"
        "Recommend iron supplements. 👍"
    )
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1st call: Cache miss -> invokes Gemini, strips emojis, persists to DB
            res1 = await ac.post(f"/users/me/documents/{doc_id}/summary", headers=headers)
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["cached"] is False
            assert "🩺" not in data1["summary"]
            assert "🩸" not in data1["summary"]
            assert "Clinical Summary" in data1["summary"]
            assert "Patient shows mild anemia." in data1["summary"]
            assert mock_client.models.generate_content.call_count == 1

            # Verify persisted in database
            async with AsyncSessionLocal() as session:
                refreshed_doc = await session.get(Document, doc_id)
                assert refreshed_doc.cached_summary == data1["summary"]

            # 2nd call: Cache hit -> immediately returns from DB
            res2 = await ac.post(f"/users/me/documents/{doc_id}/summary", headers=headers)
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["cached"] is True
            assert data2["summary"] == data1["summary"]
            # Mock count remains 1!
            assert mock_client.models.generate_content.call_count == 1

            # 3rd call with force_refresh: Re-generates
            res3 = await ac.post(f"/users/me/documents/{doc_id}/summary?force_refresh=true", headers=headers)
            assert res3.status_code == 200
            data3 = res3.json()
            assert data3["cached"] is False
            assert mock_client.models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_summary_ownership_verification():
    email1 = f"user1_{uuid.uuid4().hex[:8]}@test.com"
    email2 = f"user2_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user1 = User(email=email1, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
        user2 = User(email=email2, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
        session.add_all([user1, user2])
        await session.commit()
        await session.refresh(user1)
        await session.refresh(user2)

        doc1 = Document(user_id=user1.id, filename="user1_report.pdf")
        session.add(doc1)
        await session.commit()
        await session.refresh(doc1)
        doc1_id = doc1.id

    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login2 = await ac.post("/login", data={"username": email2, "password": TEST_PASSWORD})
            token2 = login2.json()["access_token"]
            h2 = {"Authorization": f"Bearer {token2}"}

            # User 2 attempting to access User 1's summary should return 404
            res = await ac.post(f"/users/me/documents/{doc1_id}/summary", headers=h2)
            assert res.status_code == 404
