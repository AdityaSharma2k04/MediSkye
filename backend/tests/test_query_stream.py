import uuid
import pytest
import fitz
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_query_stream_after_pdf_upload_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"query_stream_user_{uuid.uuid4().hex[:8]}@test.com"

        # 1. Register a user with memory consent
        async with AsyncSessionLocal() as session:
            user = User(
                email=email,
                hashed_password=get_password_hash(TEST_PASSWORD),
                phi_consent_granted=True,
                memory_consent_granted=True,
            )
            session.add(user)
            await session.commit()

        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload a mock PDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (50, 72),
            "Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 14.2 g/dL (ref 12.0 - 15.5) Normal. Glucose: 95 mg/dL (ref 70 - 99) Normal. Platelet count 250000 /uL."
        )
        pdf_bytes = doc.tobytes()

        upload_res = await ac.post(
            "/upload",
            files={"file": ("lab_report.pdf", pdf_bytes, "application/pdf")},
            headers=headers
        )
        assert upload_res.status_code == 200
        doc_id = upload_res.json()["document_id"]

        # 3. Mock gemini client streaming response to simulate LLM token delivery
        chunk1 = MagicMock()
        chunk1.text = "Your lab report shows normal findings. "
        chunk2 = MagicMock()
        chunk2.text = "Hemoglobin is 14.2 g/dL which is within normal limits."
        
        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]

        with patch("google.genai.Client", return_value=mock_client):
            # 4. Send query
            res = await ac.post(
                "/query",
                json={"session_id": str(doc_id), "query": "what are my values"},
                headers=headers
            )
            # 5. Asserts no exception is raised and status is 200
            assert res.status_code == 200

            stream_text = res.text
            # 6. Asserts the stream returns stage events AND content
            assert "event: stage" in stream_text
            assert "analyzing" in stream_text
            assert "retrieving" in stream_text
            assert "generating" in stream_text
            assert "Your lab report shows normal findings" in stream_text
            assert "[DONE]" in stream_text
            assert "error" not in stream_text.lower()
