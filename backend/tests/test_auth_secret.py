import pytest
import jwt
from app.core.config import settings
from app.core.auth import SECRET_KEY, create_access_token, ALGORITHM


def test_secret_key_uses_dedicated_jwt_secret():
    assert SECRET_KEY == settings.JWT_SECRET_KEY
    assert SECRET_KEY != settings.GOOGLE_API_KEY


def test_jwt_encode_decode_roundtrip():
    payload_data = {"sub": "testuser@example.com"}
    token = create_access_token(payload_data)
    assert isinstance(token, str)

    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "testuser@example.com"
    assert "exp" in decoded
    assert "jti" in decoded
