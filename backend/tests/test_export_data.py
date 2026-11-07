import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, PatientFact, DependentProfile
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_export_data_succeeds_with_dependents_and_facts():
    """Verify GET /users/me/export-data succeeds without AttributeError on fact_type or missing dependent emergency contacts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(
                email=email,
                hashed_password=get_password_hash(TEST_PASSWORD),
                phi_consent_granted=True,
                full_name="Parent User",
                emergency_contact_name="Spouse",
                emergency_contact_phone="1234567890",
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)

            dep = DependentProfile(
                user_id=user.id,
                full_name="Child Dep",
                relationship="Child",
                known_allergies="Peanuts",
            )
            s.add(dep)
            await s.commit()
            await s.refresh(dep)

            fact = PatientFact(
                user_id=user.id,
                dependent_id=dep.id,
                fact_text="Allergic to peanuts",
                fact_type="allergy",
                confidence=0.95,
            )
            doc = Document(
                user_id=user.id,
                dependent_id=dep.id,
                filename="lab.pdf",
                title="Lab Report",
            )
            s.add_all([fact, doc])
            await s.commit()
            await s.refresh(doc)

            chat = Chat(
                user_id=user.id,
                document_id=doc.id,
                dependent_id=dep.id,
                role="user",
                message="Explain lab results",
            )
            s.add(chat)
            await s.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        res = await ac.get("/users/me/export-data", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == email
        assert len(data["dependent_profiles"]) == 1
        assert data["dependent_profiles"][0]["full_name"] == "Child Dep"
        assert len(data["remembered_facts"]) == 1
        assert data["remembered_facts"][0]["fact_type"] == "allergy"
        assert len(data["documents"]) == 1
        assert len(data["documents"][0]["chat_history"]) == 1


@pytest.mark.asyncio
async def test_clear_memory_facts_self_does_not_delete_dependents():
    """Verify DELETE /users/me/memory/facts for Self deletes only Self facts and preserves dependent facts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()
            await s.refresh(user)

            dep = DependentProfile(user_id=user.id, full_name="Child", relationship="Child")
            s.add(dep)
            await s.commit()
            await s.refresh(dep)

            fact_self = PatientFact(user_id=user.id, dependent_id=None, fact_text="Self fact", fact_type="lifestyle")
            fact_dep = PatientFact(user_id=user.id, dependent_id=dep.id, fact_text="Dep fact", fact_type="allergy")
            s.add_all([fact_self, fact_dep])
            await s.commit()
            dep_id = dep.id
            user_id = user.id

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Clear facts for self
        res = await ac.delete("/users/me/memory/facts", headers=headers)
        assert res.status_code == 200

        async with AsyncSessionLocal() as s:
            facts_res = await s.execute(select(PatientFact).where(PatientFact.user_id == user_id))
            remaining_facts = facts_res.scalars().all()
            assert len(remaining_facts) == 1
            assert remaining_facts[0].dependent_id == dep_id
            assert remaining_facts[0].fact_text == "Dep fact"


@pytest.mark.asyncio
async def test_clear_memory_facts_invalid_dependent_id_returns_400():
    """Verify DELETE /users/me/memory/facts with invalid dependent_id returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"user_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        res = await ac.delete("/users/me/memory/facts?dependent_id=invalid-uuid", headers=headers)
        assert res.status_code == 400
        assert "Invalid dependent_id" in res.json()["detail"]
