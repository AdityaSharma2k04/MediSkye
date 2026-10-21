import pytest
import time
import asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from langchain_core.documents import Document

from app.main import app
from app.services.upload_jobs import clear_jobs
from tests.test_upload import get_authenticated_headers


@pytest.mark.anyio
async def test_upload_status_endpoint_never_blocked():
    """
    Verify that while a background upload task is running,
    GET /upload/status/{job_id} responds concurrently within 500ms
    proving that the asyncio event loop is never blocked.
    """
    await clear_jobs()

    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF\n"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="async_test@test.com")

        # Mock extract_text_from_file to simulate non-blocking async work
        async def mock_extract(tmp_path, filename):
            await asyncio.sleep(0.3)
            return [
                Document(page_content="Clinical Blood Test: Hemoglobin 14.2 g/dL Normal", metadata={"page": 1}),
                Document(page_content="Platelet Count: 250,000 /uL Normal Range", metadata={"page": 2}),
            ]

        # Mock acreate_hybrid_index to simulate non-blocking async embedding
        async def mock_acreate_index(page_docs, index_path):
            await asyncio.sleep(0.3)
            return None, None, page_docs

        with patch("app.api.v1.endpoints.upload.validate_file_upload"), \
             patch("app.api.v1.endpoints.upload.extract_text_from_file", side_effect=mock_extract), \
             patch("app.api.v1.endpoints.upload.acreate_hybrid_index", side_effect=mock_acreate_index), \
             patch("app.api.v1.endpoints.upload.extract_and_cache_metrics", new=AsyncMock(return_value=[])), \
             patch("app.api.v1.endpoints.upload.asave_index_artifacts", new=AsyncMock(return_value="artifacts/test")):

            # 1. Start upload (returns 202 immediately with job_id)
            upload_res = await ac.post(
                "/upload",
                files={"file": ("lab_report.pdf", pdf_bytes, "application/pdf")},
                headers=headers,
            )
            assert upload_res.status_code == 202, f"Upload initiation failed: {upload_res.text}"
            data = upload_res.json()
            job_id = data["job_id"]

            # 2. Concurrently poll GET /upload/status/{job_id} while background task is in-flight
            await asyncio.sleep(0.05)  # Let background task start and enter mock_extract

            t_poll_start = time.monotonic()
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            poll_elapsed = time.monotonic() - t_poll_start

            # 3. Assert status endpoint returned immediately without being blocked by background work
            assert status_res.status_code == 200, f"Status check failed: {status_res.text}"
            assert poll_elapsed < 0.5, f"Event loop was blocked! Poll took {poll_elapsed:.3f}s (must be < 0.5s)"
            status_data = status_res.json()
            assert status_data["status"] in ["processing", "completed"]

            # 4. Wait for background task to complete and verify final status
            max_wait = 3.0
            t_wait_start = time.monotonic()
            final_status = status_data["status"]
            while final_status != "completed" and (time.monotonic() - t_wait_start) < max_wait:
                await asyncio.sleep(0.1)
                poll = await ac.get(f"/upload/status/{job_id}", headers=headers)
                if poll.status_code == 200:
                    final_status = poll.json()["status"]

            assert final_status == "completed", f"Job failed to complete within {max_wait}s: {final_status}"
