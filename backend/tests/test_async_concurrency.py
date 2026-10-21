import uuid
import time
import json
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.llm.gemini_client import GeminiUnavailableError
from tests.conftest import TEST_PASSWORD


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    async def aembed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768

    async def aembed_query(self, text):
        return [0.1] * 768


@pytest.mark.asyncio
async def test_health_returns_promptly_during_streaming_query():
    """Verify that a slow or iterating streaming query does not block /health (event loop unblocked)."""
    email = f"async_test_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    def slow_generator():
        for i in range(3):
            time.sleep(0.3)  # simulates Gemini stream chunk latency in thread
            chunk = MagicMock()
            chunk.text = f"Chunk {i} "
            yield chunk

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = slow_generator()

    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"
    mock_client.models.generate_content.return_value = intent_response

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock, return_value=intent_response),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            query_started = asyncio.Event()

            async def run_query():
                query_started.set()
                res = await ac.post(
                    "/query",
                    headers=headers,
                    json={"session_id": str(uuid.uuid4()), "query": "What is hypertension?", "language": "English"},
                )
                return res.status_code

            async def check_health():
                await query_started.wait()
                await asyncio.sleep(0.05)  # Let query enter streaming phase
                t0 = time.perf_counter()
                res = await ac.get("/health")
                elapsed = time.perf_counter() - t0
                return res.status_code, elapsed

            query_task = asyncio.create_task(run_query())
            health_task = asyncio.create_task(check_health())

            q_status, (h_status, h_elapsed) = await asyncio.gather(query_task, health_task)

            assert q_status == 200
            assert h_status == 200
            # Health check must complete in < 500ms even though query takes ~900ms
            assert h_elapsed < 0.5, f"Health check took {h_elapsed}s, expected < 0.5s"


@pytest.mark.asyncio
async def test_stream_error_yields_done_event():
    """Verify that an exception mid-stream still emits sanitized error and 'data: [DONE]'."""
    email = f"stream_err_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    def error_generator():
        chunk = MagicMock()
        chunk.text = "Starting report explanation..."
        yield chunk
        raise RuntimeError("Internal database connection error: /var/data/secret.db")

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = error_generator()

    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"
    mock_client.models.generate_content.return_value = intent_response

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock, return_value=intent_response),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                headers=headers,
                json={"session_id": str(uuid.uuid4()), "query": "Explain test results", "language": "English"},
            )

            assert res.status_code == 200
            body_text = res.text

            # Error payload must be sanitized — no internal paths leaked
            assert "error" in body_text
            assert "/var/data/secret.db" not in body_text
            assert "An unexpected error occurred while generating the response." in body_text
            assert "data: [DONE]\n\n" in body_text


@pytest.mark.asyncio
async def test_stream_gemini_unavailable_yields_busy_message():
    """Verify that GeminiUnavailableError during streaming emits polite busy error and [DONE]."""
    email = f"stream_unavail_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    def unavailable_generator():
        raise GeminiUnavailableError("Service 503 unavailable")
        yield

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.side_effect = lambda *args, **kwargs: unavailable_generator()

    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock, return_value=intent_response),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                headers=headers,
                json={"session_id": str(uuid.uuid4()), "query": "Explain test results", "language": "English"},
            )

            assert res.status_code == 200
            body_text = res.text

            assert "error" in body_text
            assert "The AI service is temporarily busy due to high demand. Please try again in 1-2 minutes." in body_text
            assert "data: [DONE]\n\n" in body_text


@pytest.mark.asyncio
async def test_streaming_falls_back_on_first_chunk_failure():
    """Mock 3.8 to raise retryable error on the very first chunk, mock 3.6 to succeed -> assert response from 3.6."""
    email = f"stream_fallback_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    def fail_first_chunk():
        raise GeminiUnavailableError("503 Service Unavailable")
        yield

    def succeed_fallback():
        chunk = MagicMock()
        chunk.text = "Answer from gemini-3.5-flash fallback."
        yield chunk

    def stream_dispatcher(*args, **kwargs):
        model = kwargs.get("model")
        if model == "gemini-3.6-flash":
            return fail_first_chunk()
        elif model == "gemini-3.5-flash":
            return succeed_fallback()
        raise RuntimeError(f"Unexpected model called: {model}")

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.side_effect = stream_dispatcher

    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock, return_value=intent_response),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                headers=headers,
                json={"session_id": str(uuid.uuid4()), "query": "What causes headaches?", "language": "English"},
            )

            assert res.status_code == 200
            body_text = res.text
            assert "Answer from gemini-3.5-flash fallback." in body_text
            assert "data: [DONE]\n\n" in body_text
            assert mock_client.models.generate_content_stream.call_count == 2


@pytest.mark.asyncio
async def test_streaming_does_not_retry_after_partial_content():
    """Mock 3.8 to yield 2 chunks then fail -> assert no fallback attempted."""
    email = f"stream_partial_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    def partial_then_fail():
        chunk1 = MagicMock()
        chunk1.text = "Chunk one."
        yield chunk1
        chunk2 = MagicMock()
        chunk2.text = "Chunk two."
        yield chunk2
        raise RuntimeError("503 Disconnected mid-stream")

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.side_effect = lambda *args, **kwargs: partial_then_fail()

    intent_response = MagicMock()
    intent_response.text = "GENERAL_HEALTH"

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock, return_value=intent_response),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            res = await ac.post(
                "/query",
                headers=headers,
                json={"session_id": str(uuid.uuid4()), "query": "What causes headaches?", "language": "English"},
            )

            assert res.status_code == 200
            body_text = res.text
            # Verified partial chunks were streamed
            assert "Chunk one." in body_text
            assert "Chunk two." in body_text
            # Verified no fallback attempted: call_count is strictly 1
            assert mock_client.models.generate_content_stream.call_count == 1
            assert "data: [DONE]\n\n" in body_text
