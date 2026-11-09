import os
from unittest.mock import patch
import pytest

from app.core.observability import init_sentry, _before_send, _scrub, SENSITIVE_KEYS


def test_init_sentry_noop_when_dsn_unset(monkeypatch):
    """init_sentry() is a no-op when SENTRY_DSN is unset (app still boots)."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
        mock_init.assert_not_called()


def test_init_sentry_called_when_dsn_set(monkeypatch):
    """init_sentry() initializes sentry_sdk with correct security parameters when DSN is set."""
    monkeypatch.setenv("SENTRY_DSN", "https://mockpublickey@sentry.io/12345")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "test-env")
    monkeypatch.setenv("SENTRY_RELEASE", "v1.0.0")

    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
        mock_init.assert_called_once()
        _, kwargs = mock_init.call_args
        assert kwargs["dsn"] == "https://mockpublickey@sentry.io/12345"
        assert kwargs["environment"] == "test-env"
        assert kwargs["release"] == "v1.0.0"
        assert kwargs["send_default_pii"] is False
        assert kwargs["max_request_body_size"] == "never"
        assert kwargs["include_local_variables"] is False
        assert kwargs["before_send"] == _before_send
        assert kwargs["before_send_transaction"] == _before_send


def test_init_sentry_failsafe_on_invalid_dsn(monkeypatch):
    """init_sentry() does not raise and does not call sentry_sdk.init on invalid non-https DSN."""
    monkeypatch.setenv("SENTRY_DSN", "invalid-dsn-string")
    with patch("sentry_sdk.init") as mock_init:
        init_sentry()
        mock_init.assert_not_called()


def test_init_sentry_failsafe_on_init_exception(monkeypatch):
    """init_sentry() catches any sentry_sdk.init exception so app never crashes on startup."""
    monkeypatch.setenv("SENTRY_DSN", "https://mockpublickey@sentry.io/12345")
    with patch("sentry_sdk.init", side_effect=RuntimeError("Sentry connection boom")):
        # Must not raise
        init_sentry()


@pytest.mark.anyio
async def test_global_exception_handler_captures_to_sentry():
    """global_exception_handler calls sentry_sdk.capture_exception before returning 500."""
    from unittest.mock import MagicMock
    from app.middleware.error_handler import global_exception_handler
    mock_request = MagicMock()
    mock_request.state.request_id = "test-req-123"
    mock_request.method = "GET"
    mock_request.url.path = "/test-route"
    test_exc = ValueError("Unhandled test exception")
    with patch("sentry_sdk.capture_exception") as mock_capture:
        res = await global_exception_handler(mock_request, test_exc)
        assert res.status_code == 500
        mock_capture.assert_called_once_with(test_exc)


def test_before_send_strips_request_and_user_and_scrubs_exception():
    """_before_send strips 'request' & 'user' and replaces exception value with '[scrubbed exception message]'."""
    event = {
        "request": {
            "url": "https://api.mediskye.com/query",
            "headers": {"Authorization": "Bearer sensitive-token"},
            "data": {"query": "patient blood sugar level"},
        },
        "user": {
            "id": "123",
            "email": "jane@example.com",
            "username": "johndoe",
        },
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "Clinical error involving jane@example.com with glucose 250 mg/dL",
                }
            ]
        },
        "extra": {
            "email": "jane@example.com",
            "safe_key": "safe_value",
        },
        "contexts": {
            "caregiver": {"name": "Jane Doe"},
            "os": {"name": "Linux"},
        },
    }

    scrubbed = _before_send(event, hint={})

    # Stripped request and user
    assert "request" not in scrubbed
    assert "user" not in scrubbed

    # Scrubbed exception message
    assert scrubbed["exception"]["values"][0]["value"] == "[scrubbed exception message]"

    # Scrubbed extra and contexts
    assert scrubbed["extra"]["email"] == "[scrubbed]"
    assert scrubbed["extra"]["safe_key"] == "safe_value"
    assert scrubbed["contexts"]["caregiver"] == "[scrubbed]"
    assert scrubbed["contexts"]["os"]["name"] == "Linux"


def test_scrub_recursive_sensitive_keys_and_string_truncation():
    """_scrub recursively replaces keys in SENSITIVE_KEYS with '[scrubbed]' and truncates strings >256 chars."""
    long_string = "A" * 300
    expected_truncated = "A" * 256 + "...[truncated]"

    data = {
        "email": "test@mediskye.com",
        "health_profile": {"conditions": ["hypertension", "diabetes"]},
        "PASSWORD": "supersecretpassword",
        "nested": {
            "Token": "secret_jwt_token",
            "phi": {"diagnosis": "type-2 diabetes"},
            "lab_results": [{"hba1c": "7.5%"}],
            "caregiver": "Dr. Smith",
            "safe_field": "public info",
            "long_text": long_string,
        },
        "list_data": [
            {"prompt": "Tell me about my symptoms"},
            {"response": "Here is clinical diagnosis"},
            "short string",
            long_string,
        ],
    }

    result = _scrub(data)

    assert result["email"] == "[scrubbed]"
    assert result["health_profile"] == "[scrubbed]"
    assert result["PASSWORD"] == "[scrubbed]"
    assert result["nested"]["Token"] == "[scrubbed]"
    assert result["nested"]["phi"] == "[scrubbed]"
    assert result["nested"]["lab_results"] == "[scrubbed]"
    assert result["nested"]["caregiver"] == "[scrubbed]"
    assert result["nested"]["safe_field"] == "public info"
    assert result["nested"]["long_text"] == expected_truncated

    assert result["list_data"][0]["prompt"] == "[scrubbed]"
    assert result["list_data"][1]["response"] == "[scrubbed]"
    assert result["list_data"][2] == "short string"
    assert result["list_data"][3] == expected_truncated
