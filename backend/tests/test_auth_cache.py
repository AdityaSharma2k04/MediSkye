"""
Regression tests for the 60s in-memory auth token cache.

Bug: GET /users/me (and every other PHI endpoint) used get_current_user_full,
which only WROTE to the cache and never READ it, so each call re-ran the full
Firebase / JWT verification. Parallel post-login requests also each missed.
"""
import asyncio
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core import auth as auth_module
from app.core.auth import create_access_token, get_cached_user_dto, get_password_hash


async def _make_user(full_name: str = "Cache Tester") -> tuple[str, str, uuid.UUID]:
    email = f"auth_cache_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash("Password123!"),
            phi_consent_granted=True,
            full_name=full_name,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id
    return email, create_access_token(data={"sub": email}), user_id


def _counting_resolver():
    real = auth_module._resolve_user_full
    calls = {"n": 0}

    async def wrapper(token, db):
        calls["n"] += 1
        await asyncio.sleep(0.05)  # widen the race window for concurrency tests
        return await real(token, db)

    return wrapper, calls


@pytest.mark.asyncio
async def test_users_me_populates_and_hits_token_cache():
    _, token, user_id = await _make_user()
    headers = {"Authorization": f"Bearer {token}"}
    wrapper, calls = _counting_resolver()

    with patch.object(auth_module, "_resolve_user_full", wrapper):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            first = await ac.get("/users/me", headers=headers)
            assert first.status_code == 200
            assert get_cached_user_dto(token) is not None, "first /users/me must store the DTO"

            second = await ac.get("/users/me", headers=headers)
            assert second.status_code == 200
            # Lightweight endpoint shares the same cache entry
            chats = await ac.get("/users/me/chats", headers=headers)
            assert chats.status_code == 200

    assert calls["n"] == 1, f"token should be verified once, was verified {calls['n']} times"
    assert first.json()["id"] == second.json()["id"] == str(user_id)


@pytest.mark.asyncio
async def test_cached_users_me_returns_fresh_profile_after_update():
    _, token, _ = await _make_user(full_name="Before")
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/users/me", headers=headers)).json()["full_name"] == "Before"
        res = await ac.put("/users/me", json={"full_name": "After"}, headers=headers)
        assert res.status_code == 200
        assert (await ac.get("/users/me", headers=headers)).json()["full_name"] == "After"


@pytest.mark.asyncio
async def test_concurrent_first_requests_resolve_token_once():
    """GET /users/me + GET /users/me/dependents fired in parallel after login."""
    _, token, _ = await _make_user()
    headers = {"Authorization": f"Bearer {token}"}
    wrapper, calls = _counting_resolver()

    with patch.object(auth_module, "_resolve_user_full", wrapper):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            results = await asyncio.gather(
                ac.get("/users/me", headers=headers),
                ac.get("/users/me/dependents", headers=headers),
                ac.get("/users/me/documents", headers=headers),
            )

    assert [r.status_code for r in results] == [200, 200, 200]
    assert calls["n"] == 1, f"concurrent misses should coalesce, got {calls['n']} resolutions"
    assert auth_module._INFLIGHT_RESOLUTIONS == {}, "single-flight slots must be released"


@pytest.mark.asyncio
async def test_cached_token_for_deleted_user_is_rejected():
    email, token, user_id = await _make_user()
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/users/me", headers=headers)).status_code == 200
        assert get_cached_user_dto(token) is not None

        # Delete the row behind the cache's back (no eviction call)
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            await session.delete(user)
            await session.commit()

        # Mutating PHI endpoint (get_current_user_full) checks DB row existence and evicts stale cache
        res = await ac.put("/users/me", json={"full_name": "Ghost"}, headers=headers)
        assert res.status_code == 401
        assert get_cached_user_dto(token) is None

        # Subsequent GET /users/me also returns 401 now that the token is evicted
        res_get = await ac.get("/users/me", headers=headers)
        assert res_get.status_code == 401
