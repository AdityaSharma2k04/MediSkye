"""
Tests for GET /users/me/documents/{document_id}/export —
full chat transcript + cached lab metrics export as JSON.
"""

import json
import uuid
import pytest
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat
from tests.conftest import TEST_PASSWORD


async def _create_user_and_headers(ac: AsyncClient, email: str) -> tuple[str, uuid.UUID]:
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


async def _seed_document(user_id: uuid.UUID, cached_metrics=None, filename="cbc_report.pdf"):
    async with AsyncSessionLocal() as session:
        doc = Document(
            user_id=user_id,
            filename=filename,
            file_path=f"/tmp/{uuid.uuid4().hex}.index",
            title="CBC Blood Report",
            cached_metrics=cached_metrics,
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        return doc.id


async def _seed_chats(user_id: uuid.UUID, doc_id: uuid.UUID, messages):
    async with AsyncSessionLocal() as session:
        for role, text in messages:
            session.add(Chat(user_id=user_id, document_id=doc_id, role=role, message=text))
        await session.commit()


@pytest.mark.asyncio
async def test_export_returns_full_transcript_and_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await _create_user_and_headers(ac, email)

        metrics = [
            {"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "range": "12-17", "status": "Normal"},
            {"test": "LDL Cholesterol", "value": "160", "unit": "mg/dL", "range": "0-100", "status": "High"},
        ]
        doc_id = await _seed_document(user_id, cached_metrics=metrics)
        await _seed_chats(user_id, doc_id, [
            ("user", "Is my hemoglobin normal?"),
            ("ai", "Yes, your hemoglobin is within the normal range."),
        ])

        res = await ac.get(f"/users/me/documents/{doc_id}/export", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # Document metadata
        assert data["document"]["id"] == str(doc_id)
        assert data["document"]["filename"] == "cbc_report.pdf"
        assert data["document"]["title"] == "CBC Blood Report"
        assert data["document"]["created_at"] is not None

        # Messages in chronological order with both roles
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["message"] == "Is my hemoglobin normal?"
        assert data["messages"][1]["role"] == "ai"
        assert data["messages"][1]["message"] == "Yes, your hemoglobin is within the normal range."

        # Cached metrics (lab_metrics only, metrics alias removed)
        assert len(data["lab_metrics"]) == 2
        assert "metrics" not in data
        assert data["lab_metrics"][0]["test"] == "Hemoglobin"
        assert data["lab_metrics"][1]["status"] == "High"


@pytest.mark.asyncio
async def test_export_with_no_metrics_returns_empty_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await _create_user_and_headers(ac, email)
        doc_id = await _seed_document(user_id, cached_metrics=None)

        res = await ac.get(f"/users/me/documents/{doc_id}/export", headers=headers)
        assert res.status_code == 200
        assert res.json()["lab_metrics"] == []
        assert res.json()["messages"] == []


@pytest.mark.asyncio
async def test_export_parses_string_cached_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await _create_user_and_headers(ac, email)
        doc_id = await _seed_document(
            user_id,
            cached_metrics=json.dumps(
                [{"test": "TSH", "value": "0.2", "unit": "mIU/L", "range": "0.4-4.0", "status": "Low"}]
            ),
        )

        res = await ac.get(f"/users/me/documents/{doc_id}/export", headers=headers)
        assert res.status_code == 200
        assert res.json()["lab_metrics"][0]["test"] == "TSH"


@pytest.mark.asyncio
async def test_export_invalid_document_id_returns_400():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_{uuid.uuid4().hex[:8]}@test.com"
        headers, _ = await _create_user_and_headers(ac, email)
        res = await ac.get("/users/me/documents/not-a-uuid/export", headers=headers)
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_missing_document_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_{uuid.uuid4().hex[:8]}@test.com"
        headers, _ = await _create_user_and_headers(ac, email)
        res = await ac.get(f"/users/me/documents/{uuid.uuid4()}/export", headers=headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_export_cross_user_isolation_returns_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Owner creates the document
        owner_email = f"owner_{uuid.uuid4().hex[:8]}@test.com"
        _owner_headers, owner_id = await _create_user_and_headers(ac, owner_email)
        doc_id = await _seed_document(owner_id, cached_metrics=[])

        # A different user must NOT be able to export it
        intruder_email = f"intruder_{uuid.uuid4().hex[:8]}@test.com"
        intruder_headers, _ = await _create_user_and_headers(ac, intruder_email)
        res = await ac.get(f"/users/me/documents/{doc_id}/export", headers=intruder_headers)
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_export_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/users/me/documents/{uuid.uuid4()}/export")
        assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_export_my_data_returns_full_account_bundle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"export_all_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await _create_user_and_headers(ac, email)

        metrics = [
            {"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "range": "12-17", "status": "Normal"},
        ]
        doc_id = await _seed_document(user_id, cached_metrics=metrics)
        await _seed_chats(user_id, doc_id, [
            ("user", "What is my hemoglobin?"),
            ("ai", "Your hemoglobin is 14.2 g/dL."),
        ])

        res = await ac.get("/users/me/export-data", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert "profile" in data
        assert data["profile"]["email"] == email
        assert "dependent_profiles" in data
        assert "remembered_facts" in data
        assert "documents" in data
        assert len(data["documents"]) == 1
        assert data["documents"][0]["id"] == str(doc_id)
        assert len(data["documents"][0]["lab_metrics"]) == 1
        assert "metrics" not in data["documents"][0]
        assert len(data["documents"][0]["chat_history"]) == 2
        assert "export_timestamp" in data
