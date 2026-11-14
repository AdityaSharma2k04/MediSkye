import uuid
import logging
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document as LCDocument
from httpx import AsyncClient, ASGITransport
from sqlalchemy import delete
from sqlalchemy.orm.exc import StaleDataError

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_metrics_extraction_handles_deleted_document_stale_data_gracefully(caplog):
    """
    SENTRY-FIX-01: When a document is deleted while metrics extraction is in-flight,
    saving cached_metrics must catch StaleDataError, rollback, log at INFO (never ERROR),
    and return cleanly without triggering a 500 or Sentry error.
    """
    email = f"stale_metrics_{uuid.uuid4().hex[:8]}@test.com"
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
            filename="stale_test.pdf",
            file_path="dummy/path/stale.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        '[{"test": "Hemoglobin", "value": "15.0", "unit": "g/dL", "range": "13.8 - 17.2", "status": "Normal"}]'
    )

    async def side_effect_gemini(*args, **kwargs):
        # Concurrently delete the document from the DB while Gemini is "running"
        async with AsyncSessionLocal() as s2:
            await s2.execute(delete(Document).where(Document.id == doc_id))
            await s2.commit()
        return mock_response

    mock_docs = [LCDocument(page_content="Hemoglobin: 15.0 g/dL (ref 13.8 - 17.2) Normal", metadata={})]

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.metrics.call_gemini_with_retry", side_effect=side_effect_gemini),
        patch("app.api.v1.endpoints.metrics.FAISS.load_local", return_value=MagicMock()),
        patch("app.api.v1.endpoints.metrics.retrieve_relevant_docs", return_value=mock_docs),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
    ):
        with caplog.at_level(logging.INFO):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
                assert login_res.status_code == 200
                token = login_res.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}", "X-Session-ID": str(doc_id)}

                # Trigger extraction while document gets deleted in flight
                res = await ac.post("/extract-metrics", headers=headers)
                assert res.status_code == 200
                data = res.json()
                assert data["metrics"] == []

                # Assert no ERROR logs occurred in metrics endpoint
                error_records = [r for r in caplog.records if r.levelno >= logging.ERROR and "metrics" in r.name.lower()]
                assert len(error_records) == 0, f"Expected 0 ERROR logs, got: {[r.message for r in error_records]}"
                assert any("was deleted while metrics extraction was in-flight" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_document_summary_cached_only_and_stale_data_safety(caplog):
    """
    SENTRY-FIX-02:
    1. Calling GET /summary?cached_only=true when cached_summary is None returns 200 OK with summary=None and makes 0 LLM calls.
    2. If StaleDataError occurs while saving a newly generated summary, the endpoint returns 200 OK with the generated summary and does not crash.
    """
    email = f"stale_summary_{uuid.uuid4().hex[:8]}@test.com"
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
            filename="report_summary.pdf",
            file_path="dummy/path/summary.index",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Clinical Summary: Patient shows normal vitals and unremarkable blood panel."
    mock_client.models.generate_content.return_value = mock_response

    with (
        patch("google.genai.Client", return_value=mock_client),
        patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")),
        patch("app.api.v1.endpoints.query._reconstruct_document_text", return_value="Complete blood count: all markers normal."),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # ── PART 1: cached_only=true with cache miss ──
            # Must return 200 OK with summary=None and make 0 LLM calls
            res_cached_only = await ac.get(f"/users/me/documents/{doc_id}/summary?cached_only=true", headers=headers)
            assert res_cached_only.status_code == 200
            data_cached_only = res_cached_only.json()
            assert data_cached_only["summary"] is None
            assert data_cached_only["cached"] is False
            assert mock_client.models.generate_content.call_count == 0

            # ── PART 2: on-demand generation with StaleDataError on commit ──
            async def side_effect_gemini_summary(*args, **kwargs):
                # Concurrently delete the document so db.commit raises StaleDataError
                async with AsyncSessionLocal() as s2:
                    await s2.execute(delete(Document).where(Document.id == doc_id))
                    await s2.commit()
                return mock_response

            with (
                patch("app.api.v1.endpoints.query.call_gemini_with_retry", side_effect=side_effect_gemini_summary),
                caplog.at_level(logging.INFO),
            ):
                res_gen = await ac.get(f"/users/me/documents/{doc_id}/summary", headers=headers)
                assert res_gen.status_code == 200
                data_gen = res_gen.json()
                assert "Clinical Summary" in data_gen["summary"]
                assert data_gen["cached"] is False

                # Verify no ERROR logs were logged
                error_records = [r for r in caplog.records if r.levelno >= logging.ERROR and "summary" in r.name.lower()]
                assert len(error_records) == 0, f"Expected 0 ERROR logs, got: {[r.message for r in error_records]}"
                assert any("was deleted while summary generation was in-flight" in r.message for r in caplog.records)
