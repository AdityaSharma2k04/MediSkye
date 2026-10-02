import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_logout_revokes_token_via_blocklist():
    """POST /logout must blocklist the current JWT; other tokens stay valid."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"logout_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as session:
            session.add(
                User(
                    email=email,
                    hashed_password=get_password_hash(TEST_PASSWORD),
                    phi_consent_granted=True,
                )
            )
            await session.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Token is valid before logout.
        assert (await ac.get("/users/me", headers=headers)).status_code == 200

        # Logout succeeds and returns the documented payload.
        res = await ac.post("/logout", headers=headers)
        assert res.status_code == 200
        assert res.json()["message"] == "Successfully logged out"

        # The exact same token is now rejected by the blocklist.
        assert (await ac.get("/users/me", headers=headers)).status_code == 401

        # A fresh login token is unaffected (blocklist is per-jti, not per-user).
        relogin = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert relogin.status_code == 200
        new_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}
        assert (await ac.get("/users/me", headers=new_headers)).status_code == 200


@pytest.mark.asyncio
async def test_logout_without_token_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/logout")
        assert res.status_code == 401
