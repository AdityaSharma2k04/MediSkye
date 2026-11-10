import logging
import pytest
from app.core.config import settings

# Test for Fix 1: Lock Unverified JWKS Fallback & Mask Patient Emails in Logs

def test_mask_email_utility():
    from app.api.v1.endpoints.auth import _mask_email as auth_mask
    from app.services.email_service import _mask_email as svc_mask

    assert auth_mask("patient@example.com") == "p***@example.com"
    assert auth_mask("john.doe@hospital.org") == "j***@hospital.org"
    assert auth_mask("invalid") == "***"
    assert auth_mask("") == "***"
    assert auth_mask(None) == "***"

    assert svc_mask("patient@example.com") == "p***@example.com"
    assert svc_mask("invalid") == "***"


def test_mask_email_in_logger_output(caplog):
    from app.api.v1.endpoints.auth import _mask_email

    with caplog.at_level(logging.WARNING):
        logger = logging.getLogger("test_mask")
        raw_email = "sensitive_patient@example.com"
        logger.warning("Verification requested for non-existent user: %s", _mask_email(raw_email))

    assert "sensitive_patient@example.com" not in caplog.text
    assert "s***@example.com" in caplog.text


@pytest.mark.asyncio
async def test_jwks_failure_rejected_when_fallback_disabled(monkeypatch):
    import jwt
    import base64
    import json
    from app.core.auth import _resolve_user_full
    from app.db.database import AsyncSessionLocal

    # Forge an unverified RS256 token with Google issuer
    project_id = settings.GOOGLE_CLOUD_PROJECT or "mediskye-backend"
    headers = {"alg": "RS256", "kid": "fake-kid"}
    payload = {
        "iss": f"https://securetoken.google.com/{project_id}",
        "aud": project_id,
        "sub": "fake-uid-12345",
        "email": "attacker@example.com",
    }
    dummy_token = jwt.encode(payload, "test_secret_key_at_least_32_bytes_long!", algorithm="HS256")
    segments = dummy_token.split(".")
    rs256_header = base64.urlsafe_b64encode(json.dumps(headers).encode()).decode().rstrip("=")
    forged_token = f"{rs256_header}.{segments[1]}.{segments[2]}"

    monkeypatch.setattr(settings, "ENV", "development")
    monkeypatch.setattr(settings, "ALLOW_UNVERIFIED_JWT_FALLBACK", False, raising=False)

    async with AsyncSessionLocal() as session:
        # When fallback is False, _resolve_user_full MUST NOT accept the forged unverified token
        result = await _resolve_user_full(forged_token, session)
        assert result is None, f"Expected None for unverified token when ALLOW_UNVERIFIED_JWT_FALLBACK=False, got {result}"
