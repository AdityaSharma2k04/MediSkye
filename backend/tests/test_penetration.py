import uuid
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
import firebase_admin.exceptions
import firebase_admin.auth

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User


@pytest.mark.asyncio
async def test_unverified_email_password_rejection_403():
    """
    Penetration Test: An unverified email/password user must be rejected with 403 Forbidden
    across sensitive endpoints (/users/me, /users/me/documents, /query).
    """
    random_id = uuid.uuid4().hex[:8]
    test_email = f"unverified_{random_id}@example.com"
    mock_payload = {
        "uid": f"unverified_uid_{random_id}",
        "email": test_email,
        "email_verified": False,
        "firebase": {"sign_in_provider": "password"},
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_payload

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer mock_unverified_token"}

            # 1. GET /users/me
            res_user = await ac.get("/users/me", headers=headers)
            assert res_user.status_code == 403, f"Expected 403, got {res_user.status_code}"
            assert "Email not verified" in res_user.json().get("detail", "")

            # 2. GET /users/me/documents
            res_docs = await ac.get("/users/me/documents", headers=headers)
            assert res_docs.status_code == 403, f"Expected 403, got {res_docs.status_code}"
            assert "Email not verified" in res_docs.json().get("detail", "")

            # 3. POST /query
            res_query = await ac.post(
                "/query",
                headers=headers,
                json={"session_id": str(uuid.uuid4()), "query": "What are my results?"},
            )
            assert res_query.status_code == 403, f"Expected 403, got {res_query.status_code}"
            assert "Email not verified" in res_query.json().get("detail", "")


@pytest.mark.asyncio
async def test_verified_email_acceptance_200():
    """
    Penetration Test: An authenticated user with email_verified: True must be accepted (200 OK).
    """
    random_id = uuid.uuid4().hex[:8]
    test_email = f"verified_{random_id}@example.com"
    mock_payload = {
        "uid": f"verified_uid_{random_id}",
        "email": test_email,
        "email_verified": True,
        "name": "Verified User",
        "firebase": {"sign_in_provider": "password"},
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_payload

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer mock_verified_token"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            data = res.json()
            assert data["email"] == test_email


@pytest.mark.asyncio
async def test_google_oauth_bypass_unverified_flag_200():
    """
    Penetration Test: A Google OAuth user (sign_in_provider: 'google.com') is trusted by definition
    and should pass even if email_verified is absent or False.
    """
    random_id = uuid.uuid4().hex[:8]
    test_email = f"google_oauth_{random_id}@gmail.com"
    mock_payload = {
        "uid": f"google_uid_{random_id}",
        "email": test_email,
        "email_verified": False,  # Even if False, provider is google.com
        "name": "Google User",
        "firebase": {"sign_in_provider": "google.com"},
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_payload

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer mock_google_token"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
            assert res.json()["email"] == test_email


@pytest.mark.asyncio
async def test_expired_or_invalid_token_rejection_401():
    """
    Penetration Test: Expired or tampered tokens must be rejected with 401 Unauthorized.
    """
    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.side_effect = firebase_admin.exceptions.InvalidArgumentError("Invalid token")

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Invalid token header
            headers = {"Authorization": "Bearer totally_bogus_token"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 401, f"Expected 401, got {res.status_code}"
            assert res.json().get("detail") == "Could not validate credentials"

            # 2. Missing authorization header
            res_no_auth = await ac.get("/users/me")
            assert res_no_auth.status_code == 401
