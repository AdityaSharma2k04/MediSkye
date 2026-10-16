import json
import logging
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.core.logging import JSONFormatter, setup_logging, request_id_var, user_id_var


def test_json_formatter_outputs_required_keys():
    """Verify JSONFormatter outputs valid JSON containing all mandatory observability keys."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path.py",
        lineno=42,
        msg="Test structured log message",
        args=(),
        exc_info=None,
    )

    token_req = request_id_var.set("req-test-999")
    token_user = user_id_var.set("user-test-888")
    try:
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test structured log message"
        assert data["request_id"] == "req-test-999"
        assert data["user_id"] == "user-test-888"
        assert "timestamp" in data
    finally:
        request_id_var.reset(token_req)
        user_id_var.reset(token_user)


def test_setup_logging_production_uses_json():
    """Verify setup_logging configures JSONFormatter in production mode."""
    original_env = settings.ENV
    try:
        settings.ENV = "production"
        setup_logging()
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0
        assert any(isinstance(h.formatter, JSONFormatter) for h in root_logger.handlers)
    finally:
        settings.ENV = original_env
        setup_logging()


@pytest.mark.asyncio
async def test_error_response_includes_request_id():
    """Verify error responses (HTTPException) include request_id in both header and JSON body."""
    custom_id = "custom-test-req-id-555"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/users/me", headers={"X-Request-ID": custom_id})
        assert res.status_code == 401
        assert res.headers.get("X-Request-ID") == custom_id

        body = res.json()
        assert "request_id" in body
        assert body["request_id"] == custom_id
        assert "detail" in body
