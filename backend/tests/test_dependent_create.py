"""E1: create_dependent must persist lifestyle fields (not silently drop them).

Regression test for the bug where POST /users/me/dependents accepted
height_cm / diet_type / activity_level / occupation but never wrote them to
the DependentProfile row.
"""
import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


async def _auth_headers(ac: AsyncClient) -> dict:
    email = f"dep_{uuid.uuid4().hex[:8]}@test.com"
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
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_create_dependent_persists_lifestyle_fields():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _auth_headers(ac)

        payload = {
            "relationship": "child",
            "full_name": "Test Child",
            "date_of_birth": "2015-06-15",
            "biological_sex": "female",
            "blood_type": "O+",
            "height_cm": 140.5,
            "diet_type": "vegetarian",
            "activity_level": "active",
            "occupation": "student",
        }

        res = await ac.post("/users/me/dependents", json=payload, headers=headers)
        assert res.status_code == 201, res.text
        data = res.json()

        # The create response must include the previously-dropped fields.
        assert data["height_cm"] == 140.5
        assert data["diet_type"] == "vegetarian"
        assert data["activity_level"] == "active"
        assert data["occupation"] == "student"

        # ...and they must still be there on a fresh read (real persistence).
        listing = await ac.get("/users/me/dependents", headers=headers)
        assert listing.status_code == 200, listing.text
        matches = [d for d in listing.json() if d["id"] == data["id"]]
        assert len(matches) == 1
        dep = matches[0]
        assert dep["height_cm"] == 140.5
        assert dep["diet_type"] == "vegetarian"
        assert dep["activity_level"] == "active"
        assert dep["occupation"] == "student"
