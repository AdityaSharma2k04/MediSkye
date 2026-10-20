import uuid
import json
import asyncio
import pytest
import pymupdf as fitz
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from app.main import app
from app.core.config import settings
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, PatientFact, Chat
from app.api.v1.endpoints.query import _background_tasks
from tests.conftest import TEST_PASSWORD


EMBED_DIM = 768


class FakeEmbedder:
    """
    Deterministic, fully-offline embedder.

    The upload endpoint builds a FAISS index (``embed_documents``) and the query
    endpoint embeds the query for retrieval/MMR (``embed_query``). Both must be
    served locally because CI sets GOOGLE_API_KEY to a dummy value, so any real
    embedding call fails with ``400 API key not valid``.
    """

    def embed_documents(self, texts):
        return [[0.1] * EMBED_DIM for _ in texts]

    def embed_query(self, text):
        return [0.1] * EMBED_DIM

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


@pytest.mark.asyncio
async def test_query_stream_after_pdf_upload_success():
    transport = ASGITransport(app=app)

    # ── Fake Gemini client (all LLM traffic must stay offline) ──
    # Streaming answer returned by /query.
    chunk1 = MagicMock()
    chunk1.text = "Your lab report shows normal findings. "
    chunk2 = MagicMock()
    chunk2.text = "Hemoglobin is 14.2 g/dL which is within normal limits."

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]
    # Non-streaming calls: intent classification + background fact extraction.
    intent_response = MagicMock()
    intent_response.text = "DOCUMENT_QA"
    mock_client.models.generate_content.return_value = intent_response

    with (
        # Offline embeddings for the upload (FAISS build) and query (retrieval).
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        # Chat-message indexing embeds too — keep it offline.
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        # Local `from app.rag.embedder import get_embedder` call sites resolve here.
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        # Every LLM call: intent router, streaming answer, fact extraction.
        patch("google.genai.Client", return_value=mock_client),
        # Background fact extraction is fire-and-forget; stub it so it can never
        # outlive these patches and reach the network after the test body ends.
        patch(
            "app.api.v1.endpoints.query.process_chat_memory_extraction",
            new=AsyncMock(),
        ),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"query_stream_user_{uuid.uuid4().hex[:8]}@test.com"

            # 1. Register a user with memory consent
            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                    memory_consent_granted=True,
                )
                session.add(user)
                await session.commit()

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 2. Upload a mock PDF (embeddings mocked -> no Gemini call)
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text(
                (50, 72),
                "Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 14.2 g/dL (ref 12.0 - 15.5) Normal. Glucose: 95 mg/dL (ref 70 - 99) Normal. Platelet count 250000 /uL."
            )
            pdf_bytes = doc.tobytes()

            upload_res = await ac.post(
                "/upload",
                files={"file": ("lab_report.pdf", pdf_bytes, "application/pdf")},
                headers=headers
            )
            assert upload_res.status_code == 202
            job_id = upload_res.json()["job_id"]
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            assert status_res.status_code == 200
            assert status_res.json()["status"] == "completed"
            doc_id = status_res.json()["document_id"]

            # 3. Send query (retrieval + LLM stream are both mocked)
            res = await ac.post(
                "/query",
                json={"session_id": str(doc_id), "query": "what are my values"},
                headers=headers
            )
            # 4. Asserts no exception is raised and status is 200
            assert res.status_code == 200

            stream_text = res.text
            # 5. Asserts the stream returns stage events AND content
            assert "event: stage" in stream_text
            assert "analyzing" in stream_text
            assert "retrieving" in stream_text
            assert "generating" in stream_text
            assert "Your lab report shows normal findings" in stream_text
            assert "[DONE]" in stream_text
            assert "error" not in stream_text.lower()


@pytest.mark.asyncio
async def test_query_stream_memory_extraction_task_completes():
    transport = ASGITransport(app=app)

    chunk1 = MagicMock()
    chunk1.text = "Your lab report shows normal findings. "
    chunk2 = MagicMock()
    chunk2.text = "All parameters are within standard range."

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]
    intent_response = MagicMock()
    intent_response.text = "DOCUMENT_QA"
    mock_client.models.generate_content.return_value = intent_response

    mock_extraction_result = {
        "facts": [
            {
                "type": "condition",
                "text": "Hypertension Stage 1",
                "confidence": 0.95,
                "excerpt": "Diagnosed with hypertension stage 1",
            }
        ],
        "retractions": [],
    }

    with (
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("google.genai.Client", return_value=mock_client),
        patch("app.services.fact_persistence.extract_facts", new=AsyncMock(return_value=mock_extraction_result)),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"bg_task_user_{uuid.uuid4().hex[:8]}@test.com"

            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                    memory_consent_granted=True,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = user.id

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Upload mock PDF
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text(
                (50, 72),
                "Complete Medical Summary. Patient: Jane Doe. Diagnosed with Hypertension Stage 1 under active management. Blood pressure readings average 138/88 mmHg. Advised lifestyle modifications.",
            )
            pdf_bytes = doc.tobytes()

            upload_res = await ac.post(
                "/upload",
                files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
                headers=headers,
            )
            assert upload_res.status_code == 202
            job_id = upload_res.json()["job_id"]
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            assert status_res.status_code == 200
            assert status_res.json()["status"] == "completed"
            doc_id = status_res.json()["document_id"]

            # Query stream spawns background memory extraction task
            res = await ac.post(
                "/query",
                json={"session_id": str(doc_id), "query": "tell me about my diagnosis"},
                headers=headers,
            )
            assert res.status_code == 200
            assert "[DONE]" in res.text

            # Drain any tasks in _background_tasks
            if _background_tasks:
                await asyncio.gather(*list(_background_tasks), return_exceptions=True)
            else:
                await asyncio.sleep(0.3)

            # Assert task finished and fact was saved into DB
            async with AsyncSessionLocal() as session:
                facts_res = await session.execute(
                    select(PatientFact).filter(
                        PatientFact.user_id == user_id,
                        PatientFact.is_active.is_(True),
                    )
                )
                facts = facts_res.scalars().all()
                assert len(facts) >= 1
                target_fact = next((f for f in facts if f.fact_text == "Hypertension Stage 1"), None)
                assert target_fact is not None
                assert target_fact.is_active is True
                assert target_fact.confidence == 0.95


@pytest.mark.asyncio
async def test_query_stream_strips_abnormal_flags_json_block_and_emits_specialists():
    transport = ASGITransport(app=app)

    # 1. Provide mock LLM chunks ending with abnormal_flags JSON block split across chunks
    chunk1 = MagicMock()
    chunk1.text = "Your lab report shows elevated white blood cells.\n- Total WBC: **11,200 /uL** (normal is 4,000-11,000 /uL)\n"
    chunk2 = MagicMock()
    chunk2.text = "```json\n{\n  \"abnormal"
    chunk3 = MagicMock()
    chunk3.text = "_flags\": [\"wbc\"]\n}\n```"

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2, chunk3]
    intent_response = MagicMock()
    intent_response.text = "DOCUMENT_QA"
    mock_client.models.generate_content.return_value = intent_response

    with (
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"abnormal_flags_user_{uuid.uuid4().hex[:8]}@test.com"

            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                    memory_consent_granted=True,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = user.id

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            doc = fitz.open()
            page = doc.new_page()
            page.insert_text(
                (50, 72),
                "Complete Blood Count Report. Patient: Jane Doe. Total WBC count: 11,200 /uL (reference range 4,000 - 11,000 /uL). Red blood cells: 4.8 million/uL. Platelets: 250,000 /uL. All other hematology parameters within range."
            )
            pdf_bytes = doc.tobytes()

            upload_res = await ac.post(
                "/upload",
                files={"file": ("lab_report.pdf", pdf_bytes, "application/pdf")},
                headers=headers
            )
            assert upload_res.status_code == 202, f"Upload failed: {upload_res.json()}"
            job_id = upload_res.json()["job_id"]
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            assert status_res.status_code == 200
            assert status_res.json()["status"] == "completed"
            doc_id = status_res.json()["document_id"]

            res = await ac.post(
                "/query",
                json={"session_id": str(doc_id), "query": "What are my abnormal values?"},
                headers=headers
            )
            assert res.status_code == 200
            stream_text = res.text

            # Assert client receives visible content
            assert "Your lab report shows elevated white blood cells" in stream_text
            assert "Total WBC: **11,200 /uL**" in stream_text

            # Assert abnormal_flags JSON block was NOT streamed in visible token chunks
            for line in stream_text.splitlines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        continue
                    try:
                        payload = json.loads(data_str)
                        if "chunk" in payload:
                            assert "abnormal_flags" not in payload["chunk"], f"abnormal_flags leaked in chunk: {payload['chunk']}"
                            assert "```json" not in payload["chunk"], f"```json leaked in chunk: {payload['chunk']}"
                    except json.JSONDecodeError:
                        pass

            # Assert specialists event was fired with recommendations
            assert "specialists" in stream_text
            assert "Hematology" in stream_text

            # Assert stored message in database is clean (no abnormal_flags block)
            async with AsyncSessionLocal() as session:
                chat_res = await session.execute(
                    select(Chat).filter(Chat.user_id == user_id, Chat.role == "ai")
                )
                ai_chats = chat_res.scalars().all()
                assert len(ai_chats) >= 1
                for c in ai_chats:
                    assert "abnormal_flags" not in c.message
                    assert "```json" not in c.message
                    assert "Total WBC: **11,200 /uL**" in c.message


@pytest.mark.asyncio
async def test_query_uses_gemini():
    """Verify that query endpoint uses Gemini to stream responses without provider parameter."""
    transport = ASGITransport(app=app)

    chunk1 = MagicMock()
    chunk1.text = "Gemini answer: Headaches have multiple etiologies."
    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content_stream.return_value = [chunk1]

    # Intent classification mock response
    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"
    mock_gemini_client.models.generate_content.return_value = intent_response

    with (
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("google.genai.Client", return_value=mock_gemini_client),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"gemini_query_{uuid.uuid4().hex[:8]}@test.com"
            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                    memory_consent_granted=False,
                )
                session.add(user)
                await session.commit()

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                json={
                    "session_id": str(uuid.uuid4()),
                    "query": "What causes headaches?",
                },
                headers=headers,
            )
            assert res.status_code == 200
            stream_text = res.text

            # Assert Gemini streaming was called
            assert mock_gemini_client.models.generate_content_stream.called
            assert "Gemini answer: Headaches have multiple etiologies." in stream_text


