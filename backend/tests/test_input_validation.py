import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.auth import get_password_hash
from app.schemas.query import QueryRequest
from app.schemas.user import UserUpdate, PatientFactCreate
from app.schemas.dependent import DependentCreate
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_query_max_length_validation():
    """Verify that queries exceeding 2000 characters return HTTP 422 validation error."""
    email = f"query_len_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3000-character query -> must fail with 422
        long_query = "a" * 3000
        res = await ac.post(
            "/query",
            headers=headers,
            json={
                "session_id": str(uuid.uuid4()),
                "query": long_query,
                "language": "English",
            },
        )
        assert res.status_code == 422, f"Expected 422, got {res.status_code}: {res.text}"
        detail_text = str(res.json())
        assert "2000" in detail_text or "at most 2000 characters" in detail_text or "string_too_long" in detail_text


@pytest.mark.asyncio
async def test_json_body_size_limit_rejects_payload_over_1mb():
    """Verify that JSON payloads larger than 1MB are rejected with HTTP 413."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a payload > 1MB
        large_json_str = '{"data": "' + ("x" * (1_048_576 + 1024)) + '"}'
        headers = {
            "Content-Type": "application/json",
            "Content-Length": str(len(large_json_str)),
        }
        res = await ac.post("/query", content=large_json_str, headers=headers)
        assert res.status_code == 413, f"Expected 413, got {res.status_code}: {res.text}"
        assert "Request body too large" in res.json().get("detail", "")


def test_null_byte_stripped_in_schemas():
    """Verify that null bytes and control characters are stripped in Pydantic schema inputs."""
    # 1. QueryRequest
    q = QueryRequest(
        session_id=str(uuid.uuid4()),
        query="What is\x00 hypertension\x00?",
    )
    assert q.query == "What is hypertension?"

    # 2. UserUpdate
    u = UserUpdate(
        full_name="John\x00 Doe",
        occupation="Software\x00 Engineer",
        emergency_contact_name="Jane\x00 Doe",
    )
    assert u.full_name == "John Doe"
    assert u.occupation == "Software Engineer"
    assert u.emergency_contact_name == "Jane Doe"

    # 3. DependentCreate
    d = DependentCreate(
        relationship="Child\x00",
        full_name="Alex\x00 Smith",
    )
    assert d.relationship == "Child"
    assert d.full_name == "Alex Smith"

    # 4. PatientFactCreate
    f = PatientFactCreate(
        fact_type="condition",
        fact_text="Type 2\x00 Diabetes",
    )
    assert f.fact_text == "Type 2 Diabetes"
