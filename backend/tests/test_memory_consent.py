import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_memory_consent_toggle_persists_across_requests():
    """Locks in the current POST /users/me/memory/consent behaviour.

    The endpoint must flip the flag and the new state must be visible to a
    subsequent GET /users/me/memory/status (i.e. it is committed, not just
    echoed back).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"consent_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as session:
            session.add(
                User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                    memory_consent_granted=True,
                )
            )
            await session.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1. Read the initial consent state.
        res = await ac.get("/users/me/memory/status", headers=headers)
        assert res.status_code == 200
        assert res.json()["memory_consent_granted"] is True

        # 2. Toggle memory OFF.
        res = await ac.post("/users/me/memory/consent", json={"consent": False}, headers=headers)
        assert res.status_code == 200
        assert res.json()["memory_consent_granted"] is False

        # 3. The OFF state persists across a fresh request.
        res = await ac.get("/users/me/memory/status", headers=headers)
        assert res.status_code == 200
        assert res.json()["memory_consent_granted"] is False

        # 4. Toggle back ON and confirm persistence again.
        res = await ac.post("/users/me/memory/consent", json={"consent": True}, headers=headers)
        assert res.status_code == 200
        assert res.json()["memory_consent_granted"] is True

        res = await ac.get("/users/me/memory/status", headers=headers)
        assert res.json()["memory_consent_granted"] is True


@pytest.mark.asyncio
async def test_memory_consent_requires_authentication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        assert (await ac.get("/users/me/memory/status")).status_code == 401
        assert (
            await ac.post("/users/me/memory/consent", json={"consent": True})
        ).status_code == 401
