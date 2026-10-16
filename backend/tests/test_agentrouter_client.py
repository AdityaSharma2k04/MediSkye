import pytest
from unittest.mock import patch
from app.core.config import settings
from app.llm.agentrouter_client import (
    call_agentrouter,
    call_agentrouter_stream,
    AgentRouterError,
    FALLBACK_MODELS,
)


class MockStreamResponse:
    def __init__(self, status_code=200, lines=None, error_after=None, body=b""):
        self.status_code = status_code
        self.lines = lines or []
        self.error_after = error_after
        self._body = body

    async def aread(self):
        return self._body

    async def aiter_lines(self):
        count = 0
        for line in self.lines:
            if self.error_after is not None and count >= self.error_after:
                raise RuntimeError("Connection dropped mid-stream")
            yield line
            count += 1


class MockStreamClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise RuntimeError("No more mock responses")
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp

        class StreamContext:
            async def __aenter__(self_inner):
                return resp

            async def __aexit__(self_inner, exc_type, exc_val, exc_tb):
                pass

        return StreamContext()


@pytest.mark.asyncio
async def test_missing_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "AGENTROUTER_API_KEY", "")
    with pytest.raises(AgentRouterError, match="AGENTROUTER_API_KEY not configured"):
        async for _ in call_agentrouter_stream("system prompt", "user query"):
            pass


@pytest.mark.asyncio
async def test_stream_parses_sse(monkeypatch):
    monkeypatch.setattr(settings, "AGENTROUTER_API_KEY", "test-key")

    sse_lines = [
        ': ping',
        'data: {"choices": [{"delta": {"content": "Hello"}}]}',
        'data: {"choices": [{"delta": {"content": " "}}]}',
        'data: {"choices": [{"delta": {"content": "world!"}}]}',
        'data: [DONE]',
    ]
    mock_client = MockStreamClient([
        MockStreamResponse(status_code=200, lines=sse_lines),
    ])

    with patch("app.llm.agentrouter_client.httpx.AsyncClient", return_value=mock_client):
        chunks = []
        async for token in call_agentrouter_stream("system prompt", "user query"):
            chunks.append(token)

        assert "".join(chunks) == "Hello world!"
        assert len(mock_client.calls) == 1
        model_called = mock_client.calls[0][2]["json"]["model"]
        assert model_called == FALLBACK_MODELS[0]


@pytest.mark.asyncio
async def test_fallback_on_first_model_failure(monkeypatch):
    monkeypatch.setattr(settings, "AGENTROUTER_API_KEY", "test-key")

    mock_client = MockStreamClient([
        # Model 1 fails before yielding content (e.g. HTTP 500)
        MockStreamResponse(status_code=500, body=b"Internal server error"),
        # Model 2 succeeds
        MockStreamResponse(status_code=200, lines=[
            'data: {"choices": [{"delta": {"content": "Response from fallback"}}]}',
            'data: [DONE]',
        ]),
    ])

    with (
        patch("app.llm.agentrouter_client.FALLBACK_MODELS", ["primary-model", "fallback-model"]),
        patch("app.llm.agentrouter_client.httpx.AsyncClient", return_value=mock_client),
    ):
        result = await call_agentrouter("system prompt", "user query")
        assert result == "Response from fallback"
        assert len(mock_client.calls) == 2
        assert mock_client.calls[0][2]["json"]["model"] == "primary-model"
        assert mock_client.calls[1][2]["json"]["model"] == "fallback-model"


@pytest.mark.asyncio
async def test_no_fallback_after_partial_content(monkeypatch):
    monkeypatch.setattr(settings, "AGENTROUTER_API_KEY", "test-key")

    sse_lines = [
        'data: {"choices": [{"delta": {"content": "Partial"}}]}',
        'data: {"choices": [{"delta": {"content": " response"}}]}',
        'data: {"choices": [{"delta": {"content": " should not reach"}}]}',
    ]
    mock_client = MockStreamClient([
        # Model 1 yields 2 chunks then crashes mid-stream
        MockStreamResponse(status_code=200, lines=sse_lines, error_after=2),
        # Model 2 should NEVER be called
        MockStreamResponse(status_code=200, lines=[
            'data: {"choices": [{"delta": {"content": "Duplicate"}}]}',
            'data: [DONE]',
        ]),
    ])

    with (
        patch("app.llm.agentrouter_client.FALLBACK_MODELS", ["primary-model", "fallback-model"]),
        patch("app.llm.agentrouter_client.httpx.AsyncClient", return_value=mock_client),
    ):
        chunks = []
        with pytest.raises(AgentRouterError, match="Stream failed mid-response on primary-model"):
            async for token in call_agentrouter_stream("system prompt", "user query"):
                chunks.append(token)

        assert "".join(chunks) == "Partial response"
        # Ensure fallback model was NOT attempted
        assert len(mock_client.calls) == 1
        assert len(mock_client.responses) == 1


def test_fallback_models_single_deepseek():
    """Verify only deepseek-v4-flash is configured in Agent Router."""
    assert FALLBACK_MODELS == ["deepseek-v4-flash"]


@pytest.mark.asyncio
async def test_all_models_fail_mentions_gemini_dropdown(monkeypatch):
    monkeypatch.setattr(settings, "AGENTROUTER_API_KEY", "test-key")

    mock_client = MockStreamClient([
        MockStreamResponse(status_code=500, body=b"Error") for _ in FALLBACK_MODELS
    ])

    with patch("app.llm.agentrouter_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AgentRouterError, match="Please select Gemini model from the drop down menu"):
            async for _ in call_agentrouter_stream("system prompt", "user query"):
                pass

        # Verify all models in fallback hierarchy were attempted in sequence (1 request each)
        assert len(mock_client.calls) == len(FALLBACK_MODELS)
        called_models = [c[2]["json"]["model"] for c in mock_client.calls]
        assert called_models == FALLBACK_MODELS
