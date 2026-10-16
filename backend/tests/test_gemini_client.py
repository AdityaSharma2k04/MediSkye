import pytest
from unittest.mock import MagicMock
from app.llm.gemini_client import call_gemini_with_retry, GeminiUnavailableError
from app.llm.embeddings_client import embed_content_with_retry


@pytest.mark.asyncio
async def test_call_gemini_with_retry_429_retries_and_succeeds():
    mock_client = MagicMock()
    mock_success = MagicMock()
    mock_success.text = "Clinical observation"
    mock_success.usage_metadata.prompt_token_count = 15
    mock_success.usage_metadata.candidates_token_count = 25

    mock_client.models.generate_content.side_effect = [
        Exception("429 Resource Exhausted"),
        Exception("429 Rate limit exceeded"),
        mock_success,
    ]

    res = await call_gemini_with_retry(
        prompt="Analyze lab report",
        client=mock_client,
        backoff_delays=[0.01, 0.01, 0.01],
        user_id="user-123",
    )

    assert res == mock_success
    assert mock_client.models.generate_content.call_count == 3


@pytest.mark.asyncio
async def test_call_gemini_with_retry_permanent_503_raises_typed_error():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

    with pytest.raises(GeminiUnavailableError) as exc_info:
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[0.01, 0.01, 0.01],
        )

    assert "Gemini API unavailable after 3 attempts" in str(exc_info.value)
    assert mock_client.models.generate_content.call_count == 3


@pytest.mark.asyncio
async def test_embed_content_with_retry_retries_and_succeeds():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.embedding.values = [0.1, 0.2, 0.3]

    mock_client.models.embed_content.side_effect = [
        Exception("503 Service Unavailable"),
        mock_response,
    ]

    res = await embed_content_with_retry(
        contents="Hemoglobin 14.5",
        client=mock_client,
        backoff_delays=[0.01, 0.01, 0.01],
    )

    assert res == mock_response
    assert mock_client.models.embed_content.call_count == 2


@pytest.mark.asyncio
async def test_embed_content_with_retry_permanent_failure_raises_typed_error():
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = Exception("504 Gateway Timeout")

    with pytest.raises(GeminiUnavailableError):
        await embed_content_with_retry(
            contents="Blood glucose",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[0.01, 0.01, 0.01],
        )

    assert mock_client.models.embed_content.call_count == 3
