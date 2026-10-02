"""E2: access-token lifetime and integrity.

Regression tests for the bug where ACCESS_TOKEN_EXPIRE_MINUTES (7 days) was
declared but never used: create_access_token defaulted to 15 minutes, silently
logging users out mid-session.
"""
import uuid
from datetime import timedelta

import jwt
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_password_hash,
)
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


async def _make_user() -> str:
    email = f"tok_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                email=email,
                hashed_password=get_password_hash(TEST_PASSWORD),
                phi_consent_granted=True,
            )
        )
        await session.commit()
    return email


def test_default_token_lifetime_matches_configured_value():
    """Default lifetime must be 7 days, not the old hard-coded 15 minutes."""
    email = "lifetime@test.com"
    token = create_access_token({"sub": email})
    payload = jwt.decode(token, options={"verify_signature": False})

    assert "exp" in payload and "iat" in payload
    lifetime_seconds = payload["exp"] - payload["iat"]
    expected = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert abs(lifetime_seconds - expected) < 5, (
        f"expected ~{expected}s lifetime, got {lifetime_seconds}s"
    )


@pytest.mark.asyncio
async def test_tampered_signature_is_rejected():
    email = await _make_user()
    token = create_access_token({"sub": email})
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/users/me", headers={"Authorization": f"Bearer {tampered}"}
        )
        assert res.status_code == 401, res.text


@pytest.mark.asyncio
async def test_expired_token_is_rejected():
    email = await _make_user()
    expired = create_access_token({"sub": email}, expires_delta=timedelta(seconds=-10))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(
            "/users/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert res.status_code == 401, res.text
