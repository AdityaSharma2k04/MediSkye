import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.llm.gemini_client import call_gemini_with_retry, GeminiUnavailableError, FALLBACK_MODELS
from app.llm.embeddings_client import embed_content_with_retry
from app.rag.intent_router import classify_intent, QueryIntent


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
            fallback_models=["gemini-3.8-flash"],
        )

    assert "All models failed" in str(exc_info.value)
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

    with pytest.raises(GeminiUnavailableError) as exc_info:
        await embed_content_with_retry(
            contents="Blood glucose",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[0.01, 0.01, 0.01],
        )

    assert "Gemini Embeddings API unavailable after 3 attempts" in str(exc_info.value)
    assert mock_client.models.embed_content.call_count == 3


@pytest.mark.asyncio
async def test_intent_router_handles_none_response():
    mock_resp = MagicMock()
    mock_resp.text = None

    with patch("app.rag.intent_router.call_gemini_with_retry", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_resp
        intent = await classify_intent("What is my blood sugar level?", has_document=True)
        assert intent == QueryIntent.DOCUMENT_QA


@pytest.mark.asyncio
async def test_gemini_fallback_chain_triggers_on_503():
    mock_client = MagicMock()
    mock_fallback_resp = MagicMock()
    mock_fallback_resp.text = "Fallback model response"
    mock_fallback_resp.usage_metadata.prompt_token_count = 10
    mock_fallback_resp.usage_metadata.candidates_token_count = 15

    # Primary model ("gemini-3.8-flash") fails 3 times with 503,
    # then fallback model ("gemini-3.6-flash") succeeds on first attempt.
    mock_client.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable"),
        mock_fallback_resp,
    ]

    res = await call_gemini_with_retry(
        prompt="Analyze lab report",
        client=mock_client,
        max_attempts=3,
        backoff_delays=[0.001, 0.001, 0.001],
    )

    assert res == mock_fallback_resp
    assert mock_client.models.generate_content.call_count == 4
    calls = mock_client.models.generate_content.call_args_list
    assert calls[0].kwargs["model"] == "gemini-3.8-flash"
    assert calls[1].kwargs["model"] == "gemini-3.8-flash"
    assert calls[2].kwargs["model"] == "gemini-3.8-flash"
    assert calls[3].kwargs["model"] == "gemini-3.6-flash"


@pytest.mark.asyncio
async def test_gemini_fallback_chain_raises_after_all_fail():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

    with pytest.raises(GeminiUnavailableError) as exc_info:
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[0.001, 0.001, 0.001],
        )

    assert "All models failed" in str(exc_info.value)
    # 4 fallback models * 3 attempts = 12 total attempts
    assert mock_client.models.generate_content.call_count == len(FALLBACK_MODELS) * 3


@pytest.mark.asyncio
async def test_gemini_does_not_fallback_on_400():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("400 INVALID_ARGUMENT: Bad Request")

    with pytest.raises(Exception) as exc_info:
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[0.001, 0.001, 0.001],
        )

    assert "400 INVALID_ARGUMENT" in str(exc_info.value)
    # Must raise immediately on attempt 1 with no retry or fallback
    assert mock_client.models.generate_content.call_count == 1


@pytest.mark.asyncio
async def test_429_daily_quota_not_retried():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        "429 RESOURCE_EXHAUSTED: Quota exceeded for metric 'generate_content_free_tier_requests' and limit 'Requests per day'"
    )

    with pytest.raises(Exception) as exc_info:
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
            max_attempts=3,
            backoff_delays=[1.0, 4.0, 16.0],
        )

    # Must fail immediately on attempt 1 with no retry or backoff
    assert mock_client.models.generate_content.call_count == 1
    err_text = str(exc_info.value).lower()
    assert "per_day" in err_text or "generate_content_free_tier_requests" in err_text


@pytest.mark.asyncio
async def test_llm_cooldown_after_failure():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("503 Service Unavailable")

    with pytest.raises(GeminiUnavailableError):
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
            max_attempts=1,
            backoff_delays=[0.001],
            fallback_models=["gemini-3.8-flash"],
        )

    # After failure, LLM enters 5-minute cooldown.
    # Second call within 5 minutes raises GeminiUnavailableError immediately without attempting.
    mock_client.models.generate_content.reset_mock()
    with pytest.raises(GeminiUnavailableError) as exc_info:
        await call_gemini_with_retry(
            prompt="Analyze lab report",
            client=mock_client,
        )

    assert "cooldown" in str(exc_info.value).lower()
    assert mock_client.models.generate_content.call_count == 0


def test_resolved_embedding_model_strips_prefix_in_enterprise_mode(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_MODEL", "models/text-embedding-004")
    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_ENTERPRISE", False)
    assert settings.resolved_embedding_model == "models/text-embedding-004"

    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_ENTERPRISE", True)
    assert settings.resolved_embedding_model == "text-embedding-004"


def test_resolved_fallback_models_strips_prefix_in_enterprise_mode(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        settings,
        "GEMINI_FALLBACK_MODELS",
        ["models/gemini-3.8-flash", "gemini-3.6-flash"],
    )
    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_ENTERPRISE", False)
    assert settings.resolved_fallback_models == ["models/gemini-3.8-flash", "gemini-3.6-flash"]

    monkeypatch.setattr(settings, "GOOGLE_GENAI_USE_ENTERPRISE", True)
    assert settings.resolved_fallback_models == ["gemini-3.8-flash", "gemini-3.6-flash"]



