import pytest
from unittest.mock import patch
from fastapi import HTTPException
from app.core.config import settings
from app.core.security import verify_api_key


def test_verify_api_key_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "MEDISKYE_API_KEY", "")
    # Should return cleanly without requiring or checking key
    assert verify_api_key(None) is None
    assert verify_api_key("some_key") is None


def test_verify_api_key_with_wrong_key_raises_401(monkeypatch):
    monkeypatch.setattr(settings, "MEDISKYE_API_KEY", "correct-secret-api-key")
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key("wrong-key")
    assert exc_info.value.status_code == 401
    assert "Invalid or missing" in exc_info.value.detail


def test_verify_api_key_with_missing_key_raises_401(monkeypatch):
    monkeypatch.setattr(settings, "MEDISKYE_API_KEY", "correct-secret-api-key")
    with pytest.raises(HTTPException) as exc_info:
        verify_api_key(None)
    assert exc_info.value.status_code == 401


def test_verify_api_key_with_correct_key_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "MEDISKYE_API_KEY", "correct-secret-api-key")
    # Should not raise
    assert verify_api_key("correct-secret-api-key") is None


def test_verify_api_key_uses_secrets_compare_digest(monkeypatch):
    monkeypatch.setattr(settings, "MEDISKYE_API_KEY", "correct-secret-api-key")
    with patch("secrets.compare_digest", return_value=True) as mock_compare:
        verify_api_key("provided-api-key")
        mock_compare.assert_called_once_with("provided-api-key", "correct-secret-api-key")
