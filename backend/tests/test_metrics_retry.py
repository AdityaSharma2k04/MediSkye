import uuid
import time
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document as LCDocument
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_extract_metrics_retry_with_asyncio_sleep():
    email = f"metrics_retry_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="lab_test.pdf",
            file_path="dummy/path/doc.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_success_response = MagicMock()
    mock_success_response.text = (
        '[{"test": "Hemoglobin", "value": "14.5", "unit": "g/dL", "range": "13.8 - 17.2", "status": "Normal"}]'
    )
    # 1st call fails with 503, 2nd call succeeds (sleep 1.5s triggered once)
    mock_client.models.generate_content.side_effect = [
        Exception("503 Service Unavailable"),
        mock_success_response,
    ]

    mock_docs = [LCDocument(page_content="Hemoglobin: 14.5 g/dL (ref 13.8 - 17.2) Normal", metadata={})]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.metrics.FAISS.load_local", return_value=MagicMock()),
        patch("app.api.v1.endpoints.metrics.retrieve_relevant_docs", return_value=mock_docs),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]

            headers = {
                "Authorization": f"Bearer {token}",
                "X-Session-ID": str(doc_id),
            }

            start_time = time.perf_counter()
            res = await ac.post("/extract-metrics", headers=headers)
            elapsed = time.perf_counter() - start_time

            assert res.status_code == 200
            data = res.json()
            assert "metrics" in data
            assert len(data["metrics"]) == 1
            assert data["metrics"][0]["test"] == "Hemoglobin"
            assert data["metrics"][0]["value"] == "14.5"

            # Assert retry occurred with N=1.5s sleep and completed within N+0.5s window
            assert elapsed >= 1.45, f"Elapsed time {elapsed}s was less than the 1.5s retry sleep"
            assert elapsed <= 2.2, f"Elapsed time {elapsed}s exceeded the expected N+0.5s window"


@pytest.mark.asyncio
async def test_extract_metrics_filters_boilerplate_header_footer():
    email = f"metrics_filter_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="report_with_headers.pdf",
            file_path="dummy/path/doc.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '[\n'
        '  {"test": "ISO 15189", "value": "2022 Certified", "unit": "", "range": "", "status": "Normal"},\n'
        '  {"test": "Central Facility", "value": "42 Health", "unit": "Helpline", "range": "", "status": "Normal"},\n'
        '  {"test": "Patient Name", "value": "Jane Doe", "unit": "", "range": "", "status": "Normal"},\n'
        '  {"test": "Total Cholesterol", "value": "190", "unit": "mg/dL", "range": "< 200", "status": "Normal"},\n'
        '  {"test": "Hospital Lab Boulevard", "value": "Accession 12345", "unit": "", "range": "", "status": "Normal"}\n'
        ']'
    )
    mock_client.models.generate_content.return_value = mock_response

    mock_docs = [LCDocument(page_content="Header: Central Facility ISO 15189. Total Cholesterol: 190 mg/dL", metadata={})]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.metrics.FAISS.load_local", return_value=MagicMock()),
        patch("app.api.v1.endpoints.metrics.retrieve_relevant_docs", return_value=mock_docs),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]

            headers = {
                "Authorization": f"Bearer {token}",
                "X-Session-ID": str(doc_id),
            }

            res = await ac.post("/extract-metrics", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert "metrics" in data
            assert len(data["metrics"]) == 1
            assert data["metrics"][0]["test"] == "Total Cholesterol"
            assert data["metrics"][0]["value"] == "190"
            assert data["metrics"][0]["unit"] == "mg/dL"
