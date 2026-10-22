import os
import re
import json
import uuid
import asyncio
import tempfile
import pytest
import pymupdf as fitz
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.config import settings
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, ChatDocument
from app.rag.intent_router import QueryIntent
from tests.conftest import TEST_PASSWORD


from langchain_core.embeddings import Embeddings

EMBED_DIM = 768


class FakeEmbedder(Embeddings):
    """Fully-offline deterministic embedder for tests."""

    def embed_documents(self, texts):
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text):
        return [0.1] * EMBED_DIM

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)

    def __call__(self, text):
        return self.embed_query(text)


def create_mock_firebase_admin(payload):
    """Creates mock firebase_admin module and auth object."""
    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = payload

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth
    return mock_fb_admin, mock_fb_auth


# ==============================================================================
# FLOW 1: Full Firebase Auth Auto-Provisioning, Onboarding & Account Deletion
# ==============================================================================

@pytest.mark.asyncio
async def test_firebase_auth_auto_provisioning_and_lifecycle():
    transport = ASGITransport(app=app)
    rand_id1 = uuid.uuid4().hex[:8]
    fb_email1 = f"e2e_user_{rand_id1}@gmail.com"
    token_payload_with_name = {
        "uid": f"fb_uid_{rand_id1}",
        "email": fb_email1,
        "name": "E2E First User",
    }

    mock_admin1, mock_auth1 = create_mock_firebase_admin(token_payload_with_name)

    with patch.dict("sys.modules", {"firebase_admin": mock_admin1, "firebase_admin.auth": mock_auth1}):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. First-Login Auto-Provisioning
            res = await ac.get("/users/me", headers={"Authorization": "Bearer fake_token_1"})
            assert res.status_code == 200
            user_data = res.json()
            assert user_data["email"] == fb_email1
            assert user_data["full_name"] == "E2E First User"

            # Verify in DB
            async with AsyncSessionLocal() as session:
                db_res = await session.execute(select(User).filter(User.email == fb_email1))
                user_db = db_res.scalars().first()
                assert user_db is not None
                assert user_db.full_name == "E2E First User"
                assert user_db.phi_consent_granted is True
                user_id = user_db.id

            # 2. Missing `name` claim fallback edge case
            rand_id2 = uuid.uuid4().hex[:8]
            fb_email2 = f"noname_{rand_id2}@example.com"
            token_payload_no_name = {
                "uid": f"fb_uid_{rand_id2}",
                "email": fb_email2,
                # 'name' is intentionally missing
            }
            mock_auth1.verify_id_token.return_value = token_payload_no_name

            res_no_name = await ac.get("/users/me", headers={"Authorization": "Bearer fake_token_2"})
            assert res_no_name.status_code == 200
            user_data2 = res_no_name.json()
            assert user_data2["email"] == fb_email2
            assert user_data2["full_name"] == f"noname_{rand_id2}"

            # 3. Profile & Health Profile Update for User 1
            mock_auth1.verify_id_token.return_value = token_payload_with_name
            headers1 = {"Authorization": "Bearer fake_token_1"}

            update_payload = {
                "full_name": "Updated E2E Champion",
                "language_preference": "Spanish",
                "biological_sex": "Female",
                "blood_type": "O+",
                "pre_existing_conditions": "Mild Seasonal Asthma",
                "known_allergies": "Penicillin",
                "current_medications": "Albuterol inhaler PRN",
                "height_cm": 168.0,
                "diet_type": "Mediterranean",
                "activity_level": "Moderate",
            }
            put_res = await ac.put("/users/me", json=update_payload, headers=headers1)
            assert put_res.status_code == 200
            updated_data = put_res.json()
            assert updated_data["full_name"] == "Updated E2E Champion"
            assert updated_data["language_preference"] == "Spanish"
            assert updated_data["blood_type"] == "O+"
            assert updated_data["height_cm"] == 168.0

            # Re-fetch GET /users/me to verify persistence
            recheck_res = await ac.get("/users/me", headers=headers1)
            assert recheck_res.status_code == 200
            rechecked = recheck_res.json()
            assert rechecked["full_name"] == "Updated E2E Champion"
            assert rechecked["known_allergies"] == "Penicillin"

            # 4. Account Deletion & Cleanup (with physical files and DB relations)
            async with AsyncSessionLocal() as session:
                doc_id = uuid.uuid4()
                index_dir = settings.BASE_DIR / "indexes"
                index_dir.mkdir(parents=True, exist_ok=True)
                faiss_dir = index_dir / f"user_{user_id}_doc_{doc_id}.index"
                faiss_dir.mkdir(parents=True, exist_ok=True)
                (faiss_dir / "index.faiss").write_text("dummy faiss index")
                bm25_file = index_dir / f"user_{user_id}_doc_{doc_id}_bm25.pkl"
                bm25_file.write_text("dummy bm25 pickle")

                doc = Document(
                    id=doc_id,
                    user_id=user_id,
                    filename="health_summary.pdf",
                    file_path=str(faiss_dir),
                )
                chat = Chat(
                    user_id=user_id,
                    document_id=doc_id,
                    role="user",
                    message="Is my cholesterol normal?",
                )
                session.add_all([doc, chat])
                await session.commit()

            assert faiss_dir.exists()
            assert bm25_file.exists()

            del_res = await ac.delete("/users/me", headers=headers1)
            assert del_res.status_code == 204

            # Verify files were cleaned up
            assert not faiss_dir.exists()
            assert not bm25_file.exists()

            # Verify database rows are completely removed
            async with AsyncSessionLocal() as session:
                u_check = await session.execute(select(User).filter(User.id == user_id))
                assert u_check.scalars().first() is None

                d_check = await session.execute(select(Document).filter(Document.user_id == user_id))
                assert len(d_check.scalars().all()) == 0

                c_check = await session.execute(select(Chat).filter(Chat.user_id == user_id))
                assert len(c_check.scalars().all()) == 0

            # 5. Legacy Auth Endpoints Backward Compatibility
            legacy_email = f"legacy_{uuid.uuid4().hex[:8]}@example.com"
            reg_res = await ac.post("/register", json={
                "email": legacy_email,
                "password": TEST_PASSWORD,
                "phi_consent_granted": True,
            })
            assert reg_res.status_code == 200

            login_res = await ac.post("/login", data={
                "username": legacy_email,
                "password": TEST_PASSWORD,
            })
            assert login_res.status_code == 200
            assert "access_token" in login_res.json()


# ==============================================================================
# FLOW 2: Document Lifecycle, DB Caching & RAG Streaming Flow
# ==============================================================================

@pytest.mark.asyncio
async def test_document_lifecycle_db_caching_and_rag_streaming():
    transport = ASGITransport(app=app)
    user_email = f"doc_lifecycle_{uuid.uuid4().hex[:8]}@example.com"

    # Pre-create user with local auth
    async with AsyncSessionLocal() as session:
        user = User(
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    # Create mock Gemini client
    mock_client = MagicMock()

    # 1. Content for metrics extraction
    mock_metrics_resp = MagicMock()
    mock_metrics_resp.text = json.dumps([
        {"test": "Hemoglobin", "value": "14.5", "unit": "g/dL", "range": "12.0 - 15.5", "status": "Normal"},
        {"test": "ISO 15189 Certified", "value": "Valid", "unit": "N/A", "range": "", "status": "Normal"},
        {"test": "Central Facility Lab", "value": "Certified", "unit": "N/A", "range": "", "status": "Normal"},
    ])

    # 2. Content for summary generation
    mock_summary_resp = MagicMock()
    mock_summary_resp.text = "### Clinical Summary\n**Overview**: All laboratory biomarkers are within expected physiological limits.\n**Hematology**: Hemoglobin 14.5 g/dL."

    # 3. Intent router and other generate_content calls
    def fake_generate_content(*args, **kwargs):
        contents = str(kwargs.get("contents") or (args[0] if args else ""))
        if "biomarker" in contents.lower() or "medical lab data" in contents.lower():
            return mock_metrics_resp
        if "clinical summary" in contents.lower() or "printable" in contents.lower():
            return mock_summary_resp
        # Default intent
        resp = MagicMock()
        resp.text = "DOCUMENT_QA"
        return resp

    mock_client.models.generate_content.side_effect = fake_generate_content

    # Streaming chunks for query
    chunk1 = MagicMock()
    chunk1.text = "Your laboratory report indicates a normal Hemoglobin level of 14.5 g/dL. "
    chunk2 = MagicMock()
    chunk2.text = "All physiological indices are well balanced."
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]

    with (
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("app.api.v1.endpoints.metrics.get_embedder", return_value=FakeEmbedder()),
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": user_email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Generate minimal valid PDF in-memory
            pdf_doc = fitz.open()
            page = pdf_doc.new_page()
            page.insert_text(
                (50, 72),
                "Central Facility Laboratory - ISO 15189 Certified\n"
                "Patient: Alice Test. Sample ID: #98234.\n"
                "Hemoglobin: 14.5 g/dL (Reference Range: 12.0 - 15.5 g/dL) Normal.\n"
                "Total WBC: 6500 /uL (Reference: 4500 - 11000) Normal.\n"
            )
            pdf_bytes = pdf_doc.tobytes()

            # Upload PDF
            upload_res = await ac.post(
                "/upload",
                files={"file": ("clinical_report.pdf", pdf_bytes, "application/pdf")},
                headers=headers,
            )
            assert upload_res.status_code == 202
            job_id = upload_res.json()["job_id"]

            # Poll upload status until completed
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            assert status_res.status_code == 200
            assert status_res.json()["status"] == "completed"
            doc_id = status_res.json()["document_id"]
            assert doc_id is not None

            # Verify document appears in GET /users/me/documents
            docs_res = await ac.get("/users/me/documents", headers=headers)
            assert docs_res.status_code == 200
            user_docs = docs_res.json()
            assert any(d["id"] == str(doc_id) for d in user_docs)

            # Let background prewarm complete before resetting DB cache for on-demand test
            await asyncio.sleep(0.5)
            from app.api.v1.endpoints.upload import _background_warm_tasks
            if _background_warm_tasks:
                await asyncio.gather(*list(_background_warm_tasks), return_exceptions=True)

            # Ensure we reset cached_metrics to None to test the on-demand extraction flow cleanly
            async with AsyncSessionLocal() as session:
                d_obj = await session.get(Document, uuid.UUID(doc_id))
                d_obj.cached_metrics = None
                d_obj.cached_summary = None
                await session.commit()

            # Record call count before on-demand metrics
            initial_generate_calls = mock_client.models.generate_content.call_count

            # 1st call to document metrics
            metrics_res1 = await ac.get(f"/users/me/documents/{doc_id}/metrics", headers=headers)
            assert metrics_res1.status_code == 200
            metrics_data1 = metrics_res1.json()["metrics"]

            # Assert filtered biomarkers (strips ISO and Facility noise)
            assert len(metrics_data1) >= 1
            test_names = [m["test"] for m in metrics_data1]
            assert "Hemoglobin" in test_names
            assert "ISO 15189 Certified" not in test_names
            assert "Central Facility Lab" not in test_names

            # Verify doc.cached_metrics is now stored in DB
            async with AsyncSessionLocal() as session:
                d_check = await session.get(Document, uuid.UUID(doc_id))
                assert d_check.cached_metrics is not None
                assert len(d_check.cached_metrics) >= 1

            metrics_call_count_after_first = mock_client.models.generate_content.call_count
            assert metrics_call_count_after_first > initial_generate_calls

            # 2nd call to document metrics (DB CACHE HIT)
            metrics_res2 = await ac.get(f"/users/me/documents/{doc_id}/metrics", headers=headers)
            assert metrics_res2.status_code == 200
            assert metrics_res2.json()["metrics"] == metrics_data1
            # Assert LLM was NOT called again!
            assert mock_client.models.generate_content.call_count == metrics_call_count_after_first

            # Printable Summary & Cache Verification
            summary_res1 = await ac.post(f"/users/me/documents/{doc_id}/summary", headers=headers)
            assert summary_res1.status_code == 200
            summary_data1 = summary_res1.json()
            assert "Clinical Summary" in summary_data1["summary"]
            assert summary_data1["cached"] is False

            # Verify doc.cached_summary is in DB
            async with AsyncSessionLocal() as session:
                d_check = await session.get(Document, uuid.UUID(doc_id))
                assert d_check.cached_summary is not None
                assert "Clinical Summary" in d_check.cached_summary

            summary_call_count_after_first = mock_client.models.generate_content.call_count

            # 2nd call to summary (DB CACHE HIT)
            summary_res2 = await ac.post(f"/users/me/documents/{doc_id}/summary", headers=headers)
            assert summary_res2.status_code == 200
            summary_data2 = summary_res2.json()
            assert summary_data2["summary"] == summary_data1["summary"]
            assert summary_data2["cached"] is True
            # Assert LLM was NOT called again!
            assert mock_client.models.generate_content.call_count == summary_call_count_after_first

            # RAG Query & Chat Persistence
            query_res = await ac.post(
                "/query",
                json={"session_id": str(doc_id), "query": "What is my hemoglobin level?"},
                headers=headers,
            )
            assert query_res.status_code == 200
            stream_content = query_res.text

            # Verify SSE stream chunks and no deprecated specialists or raw RAG chunk strings
            assert "event: stage" in stream_content
            assert "Your laboratory report indicates a normal Hemoglobin level" in stream_content
            assert "specialists" not in stream_content
            assert "RAG chunk" not in stream_content
            assert "Disclaimer:" in stream_content
            assert "[DONE]" in stream_content

            # Multi-device Chat Sync: GET /users/me/documents/{doc_id}/chats
            chats_res = await ac.get(f"/users/me/documents/{doc_id}/chats", headers=headers)
            assert chats_res.status_code == 200
            chats = chats_res.json()
            assert len(chats) >= 2
            user_msg = next((c for c in chats if c["role"] == "user"), None)
            ai_msg = next((c for c in chats if c["role"] == "ai"), None)
            assert user_msg is not None
            assert user_msg["message"] == "What is my hemoglobin level?"
            assert ai_msg is not None
            assert "Hemoglobin" in ai_msg["message"]

            # Document Deletion
            del_doc_res = await ac.delete(f"/users/me/documents/{doc_id}", headers=headers)
            assert del_doc_res.status_code == 204

            # Verify document disappears from list
            docs_after_del = await ac.get("/users/me/documents", headers=headers)
            assert all(d["id"] != str(doc_id) for d in docs_after_del.json())


# ==============================================================================
# FLOW 3: Security Isolation (IDOR) & Edge-Case Error Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_security_isolation_and_edge_cases():
    transport = ASGITransport(app=app)

    # 1. Unauthenticated Access Protection
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        unauth_me = await ac.get("/users/me")
        assert unauth_me.status_code == 401

        unauth_query = await ac.post("/query", json={"query": "test"})
        assert unauth_query.status_code == 401

        unauth_docs = await ac.get("/users/me/documents")
        assert unauth_docs.status_code == 401

        # Invalid token
        bad_token_res = await ac.get("/users/me", headers={"Authorization": "Bearer invalid_garbage_token"})
        assert bad_token_res.status_code == 401

    # Pre-create User A and User B
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@example.com"

    async with AsyncSessionLocal() as session:
        user_a = User(
            email=user_a_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        user_b = User(
            email=user_b_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add_all([user_a, user_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)
        user_a_id = user_a.id
        user_b_id = user_b.id

        doc_a_id = uuid.uuid4()
        index_dir = settings.BASE_DIR / "indexes"
        index_dir.mkdir(parents=True, exist_ok=True)
        doc_dir = index_dir / f"user_{user_a_id}_doc_{doc_a_id}.index"
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "index.faiss").write_text("user a index data")

        doc_a = Document(
            id=doc_a_id,
            user_id=user_a_id,
            filename="user_a_confidential.pdf",
            file_path=str(doc_dir),
            cached_metrics=[{"test": "Confidential Biomarker", "value": "100", "unit": "mg/dL", "range": "0-50", "status": "High"}],
            cached_summary="Confidential summary of User A's severe condition.",
        )
        chat_a = Chat(
            user_id=user_a_id,
            document_id=doc_a_id,
            role="user",
            message="Secret PHI question from User A",
        )
        session.add_all([doc_a, chat_a])
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Login as User B
        login_b = await ac.post("/login", data={"username": user_b_email, "password": TEST_PASSWORD})
        assert login_b.status_code == 200
        token_b = login_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 2. Cross-User Isolation (IDOR) Checks
        # User B attempts to access User A's chats
        idor_chats = await ac.get(f"/users/me/documents/{doc_a_id}/chats", headers=headers_b)
        assert idor_chats.status_code in (403, 404), "User B must not view User A's document chats"

        # User B attempts to access User A's metrics
        idor_metrics = await ac.get(f"/users/me/documents/{doc_a_id}/metrics", headers=headers_b)
        assert idor_metrics.status_code in (403, 404), "User B must not view User A's metrics"

        # User B attempts to trigger/view User A's summary
        idor_summary = await ac.post(f"/users/me/documents/{doc_a_id}/summary", headers=headers_b)
        assert idor_summary.status_code in (403, 404), "User B must not access User A's summary"

        # User B attempts to query User A's document
        idor_query = await ac.post(
            "/query",
            json={"session_id": str(doc_a_id), "query": "What is the confidential biomarker?"},
            headers=headers_b,
        )
        assert idor_query.status_code in (403, 404), "User B must not query User A's document via session_id"

        # User B attempts to delete User A's document
        idor_delete = await ac.delete(f"/users/me/documents/{doc_a_id}", headers=headers_b)
        assert idor_delete.status_code in (403, 404), "User B must not delete User A's document"

        # Verify User A's document and physical files remain intact
        assert doc_dir.exists()

        # 3. Non-Existent Document Checks
        fake_uuid = str(uuid.uuid4())
        non_existent_summary = await ac.post(f"/users/me/documents/{fake_uuid}/summary", headers=headers_b)
        assert non_existent_summary.status_code == 404

        non_existent_metrics = await ac.get(f"/users/me/documents/{fake_uuid}/metrics", headers=headers_b)
        assert non_existent_metrics.status_code == 404

        non_existent_chats = await ac.get(f"/users/me/documents/{fake_uuid}/chats", headers=headers_b)
        assert non_existent_chats.status_code == 404

        invalid_id_summary = await ac.post("/users/me/documents/999999/summary", headers=headers_b)
        assert invalid_id_summary.status_code == 400

        # 4. Corrupted / Empty File Uploads
        # 0-byte file
        empty_upload = await ac.post(
            "/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            headers=headers_b,
        )
        assert empty_upload.status_code == 400

        # .exe invalid MIME/extension
        exe_upload = await ac.post(
            "/upload",
            files={"file": ("malicious.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")},
            headers=headers_b,
        )
        assert exe_upload.status_code == 400

        # Corrupted PDF
        corrupt_upload = await ac.post(
            "/upload",
            files={"file": ("broken.pdf", b"%PDF-1.4\ncorrupted junk bytes that cannot be parsed", "application/pdf")},
            headers=headers_b,
        )
        assert corrupt_upload.status_code in (400, 422)

        # 5. CASUAL Intent Fast-Path
        mock_casual_chunk = MagicMock()
        mock_casual_chunk.text = "Hello! I am MediSkye, your AI health assistant. How can I help you today?"
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = [mock_casual_chunk]

        with patch("google.genai.Client", return_value=mock_client):
            casual_res1 = await ac.post(
                "/query",
                json={"session_id": str(uuid.uuid4()), "query": "hi mediskye"},
                headers=headers_b,
            )
            assert casual_res1.status_code == 200
            casual_text1 = casual_res1.text
            assert "Hello! I am MediSkye" in casual_text1
            # Disclaimer should NOT be appended for casual greetings
            assert "Disclaimer:" not in casual_text1

            casual_res2 = await ac.post(
                "/query",
                json={"session_id": str(uuid.uuid4()), "query": "thank you"},
                headers=headers_b,
            )
            assert casual_res2.status_code == 200
            assert "Disclaimer:" not in casual_res2.text

        # 6. EMERGENCY Intent Fast-Path
        emergency_res = await ac.post(
            "/query",
            json={
                "session_id": str(uuid.uuid4()),
                "query": "I am having severe crushing chest pain and can't breathe",
            },
            headers=headers_b,
        )
        assert emergency_res.status_code == 200
        emergency_stream_text = emergency_res.text
        assert "EMERGENCY WARNING" in emergency_stream_text
        assert ("911" in emergency_stream_text or "112" in emergency_stream_text)
