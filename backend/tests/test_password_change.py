import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_password_change_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"pwd_user_{uuid.uuid4().hex[:8]}@test.com"
        old_password = TEST_PASSWORD
        new_password = "NewStrongPassword456!"

        # 1. Register user
        async with AsyncSessionLocal() as session:
            user = User(
                email=email,
                hashed_password=get_password_hash(old_password),
                phi_consent_granted=True,
            )
            session.add(user)
            await session.commit()

        # Login with initial password
        login_res = await ac.post("/login", data={"username": email, "password": old_password})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Change password with wrong current password -> 401
        res_wrong = await ac.post(
            "/users/me/password",
            json={
                "current_password": "WrongPassword123!",
                "new_password": new_password,
            },
            headers=headers,
        )
        assert res_wrong.status_code == 401
        assert "Current password is incorrect" in res_wrong.json()["detail"]

        # 3. Change password with correct current password -> 200
        res_correct = await ac.post(
            "/users/me/password",
            json={
                "current_password": old_password,
                "new_password": new_password,
            },
            headers=headers,
        )
        assert res_correct.status_code == 200
        assert res_correct.json()["message"] == "Password changed successfully"

        # 4. Login with old password -> fails (400 / 401)
        old_login = await ac.post("/login", data={"username": email, "password": old_password})
        assert old_login.status_code in [400, 401]
        assert "Incorrect email or password" in old_login.json()["detail"]

        # 5. Login with new password -> 200
        new_login = await ac.post("/login", data={"username": email, "password": new_password})
        assert new_login.status_code == 200
        assert "access_token" in new_login.json()
