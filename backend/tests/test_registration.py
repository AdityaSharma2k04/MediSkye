import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_registration_success():
    transport = ASGITransport(app=app)
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/register", json={
            "email": unique_email,
            "password": "strongPassword123",
            "phi_consent_granted": True,
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["email"] == unique_email
        assert "id" in data


@pytest.mark.asyncio
async def test_registration_rejects_password_too_short():
    transport = ASGITransport(app=app)
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/register", json={
            "email": unique_email,
            "password": "123456",  # 6 chars < 8
            "phi_consent_granted": True,
        })
        assert res.status_code == 422
        errors = res.json()["detail"]
        assert any("at least 8 characters" in str(e) for e in errors)


@pytest.mark.asyncio
async def test_registration_rejects_missing_phi_consent():
    transport = ASGITransport(app=app)
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/register", json={
            "email": unique_email,
            "password": "validPassword123",
            "phi_consent_granted": False,
        })
        assert res.status_code == 400
        assert "consent to PHI processing" in res.json()["detail"]


@pytest.mark.asyncio
async def test_registration_duplicate_email_case_insensitive():
    transport = ASGITransport(app=app)
    random_id = uuid.uuid4().hex[:8]
    email_lower = f"case_test_{random_id}@example.com"
    email_upper = f"CASE_TEST_{random_id}@EXAMPLE.COM"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # First registration
        res1 = await ac.post("/register", json={
            "email": email_lower,
            "password": "validPassword123",
            "phi_consent_granted": True,
        })
        assert res1.status_code == 200

        # Duplicate with uppercase letters
        res2 = await ac.post("/register", json={
            "email": email_upper,
            "password": "validPassword123",
            "phi_consent_granted": True,
        })
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]
