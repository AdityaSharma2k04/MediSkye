import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.limiter import limiter
from tests.conftest import TEST_PASSWORD




@pytest.mark.asyncio
async def test_register_rate_limit_triggers_429():
    """Verify that hitting /register more than 5 times per minute returns 429."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        responses = []
        for i in range(7):
            res = await ac.post(
                "/register",
                json={
                    "email": f"ratelimit_reg_{i}_{uuid.uuid4().hex[:6]}@example.com",
                    "password": TEST_PASSWORD,
                    "phi_consent_granted": True,
                },
            )
            responses.append(res.status_code)

        assert 429 in responses, f"Expected 429 rate limit in responses, got {responses}"


@pytest.mark.asyncio
async def test_login_rate_limit_triggers_429():
    """Verify that hammering /login more than 10 times per minute returns 429."""
    email = f"ratelimit_login_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        responses = []
        for _ in range(12):
            res = await ac.post(
                "/login",
                data={"username": email, "password": "wrongpassword"},
            )
            responses.append(res.status_code)

        assert 429 in responses, f"Expected 429 rate limit in responses, got {responses}"


@pytest.mark.asyncio
async def test_password_change_rate_limit_triggers_429():
    """Verify that hammering /users/me/password more than 5 times per minute returns 429."""
    email = f"ratelimit_pwd_{uuid.uuid4().hex[:6]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    from app.core.auth import create_access_token
    token = create_access_token(data={"sub": email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        responses = []
        for _ in range(7):
            res = await ac.post(
                "/users/me/password",
                headers=headers,
                json={"current_password": "wrongpassword", "new_password": "NewValidPassword123!"},
            )
            responses.append(res.status_code)

        assert 429 in responses, f"Expected 429 rate limit in responses, got {responses}"
