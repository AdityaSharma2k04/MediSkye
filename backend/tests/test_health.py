import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.anyio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data


@pytest.mark.anyio
async def test_liveness_readiness_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        liveness_res = await ac.get("/liveness")
        readiness_res = await ac.get("/readiness")
    assert liveness_res.status_code == 200
    assert readiness_res.status_code == 200


@pytest.mark.anyio
async def test_sentry_debug_captures_exception_and_returns_500(monkeypatch):
    from unittest.mock import patch
    with patch("sentry_sdk.capture_exception") as mock_capture:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as ac:
            response = await ac.get("/sentry-debug")
        assert response.status_code == 500
        data = response.json()
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        assert mock_capture.called
        assert isinstance(mock_capture.call_args[0][0], ZeroDivisionError)
