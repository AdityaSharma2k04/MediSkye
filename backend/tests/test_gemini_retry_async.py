import time
import asyncio
import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.llm.gemini_client import call_gemini_with_retry


@pytest.mark.asyncio
async def test_call_gemini_retry_does_not_block_event_loop():
    """
    Verify that backoff sleep in call_gemini_with_retry uses asyncio.sleep
    and does not block the async event loop, allowing /health to respond in < 100ms.
    """
    mock_client = MagicMock()
    mock_success = MagicMock()
    mock_success.text = "Healthy observation"

    # Attempt 1: 429 -> triggers backoff sleep of 1.0s
    # Attempt 2: Success
    mock_client.models.generate_content.side_effect = [
        Exception("429 Resource Exhausted"),
        mock_success,
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Launch retry wrapper with 1.0s backoff delay
        gemini_task = asyncio.create_task(
            call_gemini_with_retry(
                prompt="Analyze health check",
                client=mock_client,
                backoff_delays=[1.0, 4.0, 16.0],
            )
        )

        # Let the task run, encounter 429, and enter asyncio.sleep(1.0)
        await asyncio.sleep(0.1)

        # Concurrently request /health on the same event loop
        start_time = time.perf_counter()
        health_res = await ac.get("/health")
        health_elapsed = time.perf_counter() - start_time

        assert health_res.status_code == 200
        assert health_elapsed < 0.1, f"/health took {health_elapsed*1000:.1f}ms, expected < 100ms"

        # Await completion of the gemini task
        result = await gemini_task
        assert result == mock_success
        assert mock_client.models.generate_content.call_count == 2
