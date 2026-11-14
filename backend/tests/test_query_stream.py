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

            from app.api.v1.endpoints.upload import _background_warm_tasks
            if _background_warm_tasks:
                await asyncio.gather(*list(_background_warm_tasks), return_exceptions=True)


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

            # Drain any tasks in _background_tasks and _background_warm_tasks
            from app.api.v1.endpoints.upload import _background_warm_tasks
            tasks_to_drain = list(_background_tasks) + list(_background_warm_tasks)
            if tasks_to_drain:
                await asyncio.gather(*tasks_to_drain, return_exceptions=True)
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
                target_fact = next((f for f in facts if "Hypertension Stage 1" in f.fact_text), None)
                assert target_fact is not None
                assert "report.pdf" in target_fact.fact_text
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

            # Assert specialists event is NOT emitted
            assert "specialists" not in stream_text

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

            from app.api.v1.endpoints.upload import _background_warm_tasks
            if _background_warm_tasks:
                await asyncio.gather(*list(_background_warm_tasks), return_exceptions=True)


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


@pytest.mark.asyncio
async def test_query_stream_casual_intent_no_disclaimer_persists_chat():
    """Verify that casual queries stream friendly response without medical disclaimer and persist turns in DB."""
    from app.rag.safety import DISCLAIMER_TEXT

    transport = ASGITransport(app=app)
    chunk1 = MagicMock()
    chunk1.text = "Hello! I am MediSkye, ready to help you analyze your lab reports."

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk1]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"casual_user_{uuid.uuid4().hex[:8]}@test.com"

            async with AsyncSessionLocal() as session:
                user = User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                user_id = user.id

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                json={
                    "session_id": str(uuid.uuid4()),
                    "query": "hi mediskye",
                },
                headers=headers,
            )
            assert res.status_code == 200
            stream_text = res.text

            # Response content present
            assert "Hello! I am MediSkye" in stream_text

            # Disclaimer MUST NOT be in stream_text for casual intent
            assert DISCLAIMER_TEXT.strip() not in stream_text

            # Specialists MUST NOT be emitted
            assert "specialists" not in stream_text

            # Both user message and AI response must be persisted in database
            async with AsyncSessionLocal() as session:
                user_chat = (
                    await session.execute(
                        select(Chat).filter(Chat.user_id == user_id, Chat.role == "user")
                    )
                ).scalars().first()
                assert user_chat is not None
                assert user_chat.message == "hi mediskye"

                ai_chat = (
                    await session.execute(
                        select(Chat).filter(Chat.user_id == user_id, Chat.role == "ai")
                    )
                ).scalars().first()
                assert ai_chat is not None
                assert "Hello! I am MediSkye" in ai_chat.message
                assert DISCLAIMER_TEXT.strip() not in ai_chat.message


@pytest.mark.asyncio
async def test_emergency_keywords_with_document_show_banner_and_answer():
    """Regression: MEDICAL emergency + attached document must not crash the stream."""
    transport = ASGITransport(app=app)
    chunk = MagicMock()
    chunk.text = "Hemoglobin is 14.2 g/dL which is within normal limits."
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk]
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
            email = f"emerg_doc_{uuid.uuid4().hex[:8]}@test.com"
            async with AsyncSessionLocal() as session:
                session.add(User(email=email, hashed_password=get_password_hash(TEST_PASSWORD),
                                 phi_consent_granted=True, memory_consent_granted=True))
                await session.commit()
            login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            pdf = fitz.open()
            pdf.new_page().insert_text(
                (50, 72),
                "CBC Report. Hemoglobin: 14.2 g/dL (ref 12.0 - 15.5) Normal. Complete blood count examination reveals normal values across all parameters.",
            )
            up = await ac.post("/upload", files={"file": ("lab.pdf", pdf.tobytes(), "application/pdf")}, headers=headers)
            assert up.status_code == 202
            st = await ac.get(f"/upload/status/{up.json()['job_id']}", headers=headers)
            doc_id = st.json()["document_id"]

            res = await ac.post(
                "/query",
                json={"session_id": str(doc_id),
                      "query": "I am having severe chest pain and pressure. Is my hemoglobin okay?"},
                headers=headers,
            )
            assert res.status_code == 200
            assert "EMERGENCY WARNING" in res.text
            assert "Hemoglobin is 14.2" in res.text
            assert "[DONE]" in res.text

            from app.api.v1.endpoints.upload import _background_warm_tasks
            if _background_warm_tasks:
                await asyncio.gather(*list(_background_warm_tasks), return_exceptions=True)


def test_deterministic_token_boundary_abnormal_flags_stripping():
    sample_response = (
        "Your abnormal JSON-formatted lab sheet shows mild shifts.\n"
        '~~~json\n{"abnormal_flags": [{"biomarker": "LDL", "status": "High"}]}\n~~~'
    )
    expected_visible = "Your abnormal JSON-formatted lab sheet shows mild shifts.\n"

    def run_stream(chunks):
        pending_buffer = ""
        in_json_block = False
        emitted_chunks = []

        for chunk_text in chunks:
            if not chunk_text:
                continue
            if in_json_block:
                continue

            pending_buffer += chunk_text
            lower_buf = pending_buffer.lower()

            has_fence = False
            fence_idx = -1
            for fence in ("```", "~~~"):
                idx = lower_buf.find(fence)
                if idx != -1:
                    if fence_idx == -1 or idx < fence_idx:
                        fence_idx = idx
                        has_fence = True

            if has_fence:
                tail = pending_buffer[fence_idx:]
                if "abnormal_flags" in tail:
                    in_json_block = True
                    visible_chunk = pending_buffer[:fence_idx]
                    if visible_chunk:
                        emitted_chunks.append(visible_chunk)
                    pending_buffer = ""
                elif len(tail) < 150:
                    if fence_idx > 0:
                        visible_chunk = pending_buffer[:fence_idx]
                        emitted_chunks.append(visible_chunk)
                        pending_buffer = pending_buffer[fence_idx:]
                else:
                    emitted_chunks.append(pending_buffer)
                    pending_buffer = ""
            else:
                if pending_buffer.endswith(("``", "~~")):
                    to_yield = pending_buffer[:-2]
                    pending_buffer = pending_buffer[-2:]
                elif pending_buffer.endswith(("`", "~")):
                    to_yield = pending_buffer[:-1]
                    pending_buffer = pending_buffer[-1:]
                else:
                    to_yield = pending_buffer
                    pending_buffer = ""

                if to_yield:
                    emitted_chunks.append(to_yield)

        if pending_buffer and not in_json_block:
            lower_pending = pending_buffer.lower()
            fences_found = [lower_pending.find(f) for f in ("```", "~~~") if lower_pending.find(f) != -1]
            if "abnormal_flags" in lower_pending and fences_found:
                fence_idx = min(fences_found)
                visible_chunk = pending_buffer[:fence_idx]
                if visible_chunk:
                    emitted_chunks.append(visible_chunk)
            else:
                emitted_chunks.append(pending_buffer)
            pending_buffer = ""

        return "".join(emitted_chunks)

    results = {}
    for step in (2, 7):
        chunks = [sample_response[i : i + step] for i in range(0, len(sample_response), step)]
        visible = run_stream(chunks)
        results[step] = visible
        assert visible == expected_visible, f"Mismatch at step {step}: got {visible!r}"
        assert "abnormal_flags" not in visible

    assert results[2] == results[7] == expected_visible


@pytest.mark.asyncio
async def test_query_stream_retries_across_fallback_models_until_success():
    """Verify that if the first 4 models fail, the 5th model succeeds and streams answer without failing."""
    from app.llm.gemini_client import reset_cooldown
    reset_cooldown()
    transport = ASGITransport(app=app)

    models_attempted = []

    def mock_generate_stream(model, contents, config):
        models_attempted.append(model)
        if len(models_attempted) < 5:
            raise RuntimeError(f"Simulated rate limit on {model}")
        chunk = MagicMock()
        chunk.text = f"Fifth model ({model}) successfully answered your question."
        return [chunk]

    mock_gemini_client = MagicMock()
    mock_gemini_client.models.generate_content_stream.side_effect = mock_generate_stream

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
            email = f"query_fallback_{uuid.uuid4().hex[:8]}@test.com"
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

            assert len(models_attempted) == 5
            assert "Fifth model" in stream_text, f"FULL STREAM TEXT: {stream_text}"




