import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


async def get_authenticated_headers(
    ac: AsyncClient,
    email: str = "report1@test.com",
    password: str = TEST_PASSWORD
) -> dict:
    """Ensures test user exists in DB and returns valid auth headers via login."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        if not user:
            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                phi_consent_granted=True,
                consent_timestamp=datetime.utcnow()
            )
            session.add(user)
        else:
            user.hashed_password = get_password_hash(password)
            session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={
        "username": email,
        "password": password,
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_upload_missing_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/upload", files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_invalid_non_pdf_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="report1@test.com")
        response = await ac.post(
            "/upload",
            files={"file": ("test.txt", b"Hello world text file", "text/plain")},
            headers=headers
        )
    assert response.status_code in [400, 422]


@pytest.mark.anyio
async def test_upload_empty_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="report1@test.com")
        response = await ac.post(
            "/upload",
            files={"file": ("test.pdf", b"", "application/pdf")},
            headers=headers
        )
    assert response.status_code in [400, 422]
