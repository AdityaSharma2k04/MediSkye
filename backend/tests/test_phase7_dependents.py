import pytest
import uuid
from datetime import date, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.services.patient_service import calculate_age
from app.db.database import AsyncSessionLocal
from app.db.models import DependentProfile, AuditLog
from sqlalchemy import text

def test_calculate_age_utility():
    # Born exactly 25 years ago
    today = date.today()
    dob_25 = date(today.year - 25, today.month, today.day)
    assert calculate_age(dob_25) == 25
    assert calculate_age(None) is None


@pytest.mark.anyio
async def test_phase7_dependents_full_lifecycle():

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Register a test user
        email = f"caregiver_{uuid.uuid4().hex[:8]}@example.com"
        reg_res = await ac.post("/register", json={
            "email": email,
            "password": "SecurePassword123!",
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200, reg_res.text

        # 2. Login to get token
        login_res = await ac.post("/login", data={
            "username": email,
            "password": "SecurePassword123!",
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # 3. Update User Profile with new Phase 7 fields
        update_user_res = await ac.put("/users/me", json={
            "full_name": "Dr. Sarah Caregiver",
            "current_medications": "Metformin 500mg daily",
            "language_preference": "Spanish",
            "date_of_birth": "1980-05-15",
            "biological_sex": "Female"
        }, headers=auth_headers)
        assert update_user_res.status_code == 200
        user_data = update_user_res.json()
        assert user_data["current_medications"] == "Metformin 500mg daily"
        assert user_data["language_preference"] == "Spanish"
        assert user_data["calculated_age"] is not None

        # 4. Create a Dependent Profile
        create_dep_res = await ac.post("/users/me/dependents", json={
            "relationship": "Father",
            "full_name": "Robert Caregiver",
            "date_of_birth": "1950-01-10",
            "biological_sex": "Male",
            "blood_type": "O+",
            "pre_existing_conditions": "Hypertension, Type 2 Diabetes",
            "known_allergies": "Penicillin",
            "current_medications": "Lisinopril 10mg, Glipizide 5mg",
        }, headers=auth_headers)
        assert create_dep_res.status_code == 201, create_dep_res.text
        dep_data = create_dep_res.json()
        dep_id = dep_data["id"]
        assert dep_data["relationship"] == "Father"
        assert dep_data["full_name"] == "Robert Caregiver"
        assert dep_data["calculated_age"] >= 70
        assert dep_data["current_medications"] == "Lisinopril 10mg, Glipizide 5mg"

        # 5. Verify Fernet Encryption in DB for the Dependent
        async with AsyncSessionLocal() as session:
            # Raw SQL query to check that the database does NOT store plaintext PHI
            raw_res = await session.execute(
                text(f"SELECT blood_type, pre_existing_conditions, current_medications FROM dependent_profiles WHERE id = '{uuid.UUID(dep_id).hex}'")
            )
            raw_row = raw_res.first()
            assert raw_row is not None
            # The raw stored string must NOT equal the plaintext
            assert raw_row[0] != "O+"
            assert "Hypertension" not in raw_row[1]
            assert "Lisinopril" not in raw_row[2]
            # It should look like Fernet ciphertext (starts with gAAAAA)
            assert raw_row[0].startswith("gAAAAA")


        # 6. List Dependents
        list_res = await ac.get("/users/me/dependents", headers=auth_headers)
        assert list_res.status_code == 200
        deps = list_res.json()
        assert len(deps) == 1
        assert deps[0]["id"] == dep_id

        # 7. Update Dependent
        update_dep_res = await ac.put(f"/users/me/dependents/{dep_id}", json={
            "current_medications": "Lisinopril 20mg, Glipizide 5mg",
        }, headers=auth_headers)
        assert update_dep_res.status_code == 200
        assert update_dep_res.json()["current_medications"] == "Lisinopril 20mg, Glipizide 5mg"

        # 8. Check Audit Log
        async with AsyncSessionLocal() as session:
            audit_res = await session.execute(
                select(AuditLog).filter(AuditLog.dependent_id == uuid.UUID(dep_id))
            )
            audits = audit_res.scalars().all()
            actions = [a.action_type for a in audits]
            assert "DEPENDENT_CREATED" in actions
            assert "DEPENDENT_UPDATED" in actions

        # 9. Delete Dependent
        del_res = await ac.delete(f"/users/me/dependents/{dep_id}", headers=auth_headers)
        assert del_res.status_code == 204

        # Verify deletion
        list_after_del = await ac.get("/users/me/dependents", headers=auth_headers)
        assert len(list_after_del.json()) == 0
