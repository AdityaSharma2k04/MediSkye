import uuid
import pytest
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, PatientFact
from tests.conftest import TEST_PASSWORD


async def create_user_and_get_headers(ac: AsyncClient, email: str) -> dict:
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_facts_api_crud_self():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"crud_user_{uuid.uuid4().hex[:8]}@test.com"
        headers = await create_user_and_get_headers(ac, email)

        # 1. CREATE manual fact
        create_payload = {
            "fact_type": "condition",
            "fact_text": "Type 2 diabetes diagnosed 2019",
        }
        res_create = await ac.post("/users/me/facts", json=create_payload, headers=headers)
        assert res_create.status_code == 201
        created = res_create.json()
        fact_id = created["id"]
        assert created["fact_type"] == "condition"
        assert created["fact_text"] == "Type 2 diabetes diagnosed 2019"
        assert created["source_type"] == "user_edit"
        assert created["confidence"] == 1.0
        assert created["is_user_verified"] is True
        assert created["is_active"] is True

        # 2. READ facts
        res_get = await ac.get("/users/me/facts", headers=headers)
        assert res_get.status_code == 200
        facts = res_get.json()
        assert len(facts) == 1
        assert facts[0]["id"] == fact_id

        # 3. UPDATE fact (PATCH)
        patch_payload = {
            "fact_text": "Type 2 diabetes diagnosed in early 2019, controlled with diet & meds",
        }
        res_patch = await ac.patch(f"/users/me/facts/{fact_id}", json=patch_payload, headers=headers)
        assert res_patch.status_code == 200
        updated = res_patch.json()
        assert updated["fact_text"] == patch_payload["fact_text"]

        # 4. DELETE fact (soft delete)
        res_del = await ac.delete(f"/users/me/facts/{fact_id}", headers=headers)
        assert res_del.status_code == 200

        # Verify fact no longer in active list
        res_get_after = await ac.get("/users/me/facts", headers=headers)
        assert len(res_get_after.json()) == 0


@pytest.mark.asyncio
async def test_facts_api_dependent_isolation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"iso_user_{uuid.uuid4().hex[:8]}@test.com"
        headers = await create_user_and_get_headers(ac, email)

        # Create a dependent
        dep_res = await ac.post("/users/me/dependents", json={
            "relationship": "Child",
            "full_name": "Junior",
            "date_of_birth": "2015-05-10",
            "biological_sex": "Male"
        }, headers=headers)
        assert dep_res.status_code == 201
        dep_id = dep_res.json()["id"]

        # Add a fact for Self
        await ac.post("/users/me/facts", json={
            "fact_type": "condition",
            "fact_text": "Adult Hypertension",
        }, headers=headers)

        # Add a fact for Dependent
        await ac.post("/users/me/facts", json={
            "fact_type": "allergy",
            "fact_text": "Child Peanut Allergy",
            "dependent_id": dep_id,
        }, headers=headers)

        # GET /users/me/facts (Self only) — dependent fact must NOT leak
        self_res = await ac.get("/users/me/facts", headers=headers)
        self_facts = self_res.json()
        assert len(self_facts) == 1
        assert self_facts[0]["fact_text"] == "Adult Hypertension"

        # GET /users/me/facts?dependent_id={dep_id} (Dependent only)
        dep_facts_res = await ac.get(f"/users/me/facts?dependent_id={dep_id}", headers=headers)
        dep_facts = dep_facts_res.json()
        assert len(dep_facts) == 1
        assert dep_facts[0]["fact_text"] == "Child Peanut Allergy"


@pytest.mark.asyncio
async def test_facts_api_cross_user_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        user_a_headers = await create_user_and_get_headers(ac, f"user_a_{uuid.uuid4().hex[:8]}@test.com")
        user_b_headers = await create_user_and_get_headers(ac, f"user_b_{uuid.uuid4().hex[:8]}@test.com")

        # User A creates a fact
        res_create = await ac.post("/users/me/facts", json={
            "fact_type": "condition",
            "fact_text": "Confidential User A condition",
        }, headers=user_a_headers)
        assert res_create.status_code == 201
        fact_id = res_create.json()["id"]

        # User B tries to PATCH User A's fact -> MUST return 404 (not 403)
        res_patch = await ac.patch(f"/users/me/facts/{fact_id}", json={
            "fact_text": "Hacked condition",
        }, headers=user_b_headers)
        assert res_patch.status_code == 404

        # User B tries to DELETE User A's fact -> MUST return 404 (not 403)
        res_del = await ac.delete(f"/users/me/facts/{fact_id}", headers=user_b_headers)
        assert res_del.status_code == 404
