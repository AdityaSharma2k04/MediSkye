import asyncio
import time
import pytest
from unittest.mock import MagicMock
from app.llm.embeddings_client import embed_content_with_retry

# Test for Fix 3: Enforce Embeddings Timeout & Retry on TimeoutError

@pytest.mark.asyncio
async def test_embed_content_with_retry_times_out_and_retries(monkeypatch):
    attempts = 0

    def mock_sync_embed(api_client, model, contents, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            time.sleep(0.15)  # Sleeps past timeout=0.05
            return MagicMock(embedding=MagicMock(values=[0.1, 0.2]))
        # Attempt 2 succeeds immediately
        return MagicMock(embedding=MagicMock(values=[0.3, 0.4]))

    monkeypatch.setattr("app.llm.embeddings_client._sync_embed_content", mock_sync_embed)

    mock_client = MagicMock()
    result = await embed_content_with_retry(
        contents="Blood test glucose results",
        client=mock_client,
        timeout=0.05,
        max_attempts=3,
        backoff_delays=[0.01, 0.01, 0.01],
    )

    assert attempts == 2, f"Expected 2 attempts (first timed out, second succeeded), but got {attempts}"
    assert result.embedding.values == [0.3, 0.4]
