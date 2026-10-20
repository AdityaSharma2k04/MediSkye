import pytest
import uuid
from datetime import datetime, UTC
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User
from tests.conftest import TEST_PASSWORD


async def get_authenticated_headers(
    ac: AsyncClient,
    email: str = "report1@test.com",
    password: str = TEST_PASSWORD
) -> dict:
    """Ensures test user exists in DB and returns valid auth headers via login."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        if not user:
            user = User(
                email=email,
                hashed_password=get_password_hash(password),
                phi_consent_granted=True,
                consent_timestamp=datetime.now(UTC)
            )
            session.add(user)
        else:
            user.hashed_password = get_password_hash(password)
            session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={
        "username": email,
        "password": password,
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_upload_missing_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/upload", files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_upload_invalid_non_pdf_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="report1@test.com")
        response = await ac.post(
            "/upload",
            files={"file": ("test.txt", b"Hello world text file", "text/plain")},
            headers=headers
        )
    assert response.status_code in [400, 422]


@pytest.mark.anyio
async def test_upload_empty_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="report1@test.com")
        response = await ac.post(
            "/upload",
            files={"file": ("test.pdf", b"", "application/pdf")},
            headers=headers
        )
    assert response.status_code in [400, 422]


class FakeEmbedder:
    def embed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    async def aembed_documents(self, texts):
        return [[0.1] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.1] * 768

    async def aembed_query(self, text):
        return [0.1] * 768


@pytest.mark.anyio
async def test_upload_returns_202_with_job_id():
    import pymupdf as fitz
    from app.services.upload_jobs import clear_jobs
    await clear_jobs()

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 13.5 g/dL (ref range 12.0 - 15.5 g/dL) Normal. Fasting Glucose: 95 mg/dL."
    )
    pdf_bytes = doc.tobytes()

    from unittest.mock import AsyncMock
    from langchain_core.documents import Document as LCDocument

    mock_docs = [
        LCDocument(
            page_content="Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 13.5 g/dL Normal.",
            metadata={"page": 1}
        )
    ]

    transport = ASGITransport(app=app)
    with (
        patch("app.api.v1.endpoints.upload.extract_text_from_file", new=AsyncMock(return_value=mock_docs)),
        patch("app.api.v1.endpoints.upload.acreate_hybrid_index", new=AsyncMock(return_value=(None, None, mock_docs))),
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = await get_authenticated_headers(ac, email="upload_user_202@test.com")
            start_time = datetime.now()
            response = await ac.post(
                "/upload",
                files={"file": ("report.pdf", pdf_bytes, "application/pdf")},
                headers=headers
            )
            duration = (datetime.now() - start_time).total_seconds()

    assert response.status_code == 202
    assert duration < 5.0  # Returns fast (< 1-5s)
    data = response.json()
    assert "job_id" in data
    assert "status_url" in data
    assert data["status_url"] == f"/upload/status/{data['job_id']}"


@pytest.mark.anyio
async def test_upload_status_endpoint():
    from app.services.upload_jobs import create_job, update_job, clear_jobs, UploadStatus
    await clear_jobs()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await get_authenticated_headers(ac, email="status_user@test.com")

        # 1. Fetch user ID from DB
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == "status_user@test.com"))
            user = user_res.scalars().first()
            user_id = str(user.id)

        # 2. Test initial pending status
        job_id = await create_job(user_id)
        res = await ac.get(f"/upload/status/{job_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == job_id
        assert data["status"] == UploadStatus.PENDING
        assert data["document_id"] is None
        assert data["error"] is None

        # 3. Test completed status
        await update_job(job_id, status=UploadStatus.COMPLETED, document_id="doc-uuid-1234")
        res_comp = await ac.get(f"/upload/status/{job_id}", headers=headers)
        assert res_comp.status_code == 200
        data_comp = res_comp.json()
        assert data_comp["status"] == UploadStatus.COMPLETED
        assert data_comp["document_id"] == "doc-uuid-1234"

        # 4. Test 404 for non-existent job
        res_404 = await ac.get(f"/upload/status/{uuid.uuid4()}", headers=headers)
        assert res_404.status_code == 404
        assert res_404.json()["detail"] == "Job not found"


@pytest.mark.anyio
async def test_upload_job_ownership():
    from app.services.upload_jobs import create_job, clear_jobs
    await clear_jobs()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers_a = await get_authenticated_headers(ac, email="user_a@test.com")
        headers_b = await get_authenticated_headers(ac, email="user_b@test.com")

        async with AsyncSessionLocal() as session:
            user_a = (await session.execute(select(User).filter(User.email == "user_a@test.com"))).scalars().first()
            user_a_id = str(user_a.id)

        # Create job belonging to User A
        job_id_a = await create_job(user_a_id)

        # User A can view their own job
        res_a = await ac.get(f"/upload/status/{job_id_a}", headers=headers_a)
        assert res_a.status_code == 200

        # User B cannot view User A's job -> 403 Forbidden
        res_b = await ac.get(f"/upload/status/{job_id_a}", headers=headers_b)
        assert res_b.status_code == 403
        assert res_b.json()["detail"] == "Not your job"


@pytest.mark.anyio
async def test_background_task_creates_own_db_session():
    """Verify that process_upload_background creates its own DB session independently."""
    import tempfile
    import os
    from app.services.upload_jobs import create_job, get_job, UploadStatus
    from app.api.v1.endpoints.upload import process_upload_background

    # Create dummy user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await get_authenticated_headers(ac, email="bg_session_user@test.com")

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).filter(User.email == "bg_session_user@test.com"))).scalars().first()
        user_id = str(user.id)

    job_id = await create_job(user_id)

    # Create a small temp text file as mock upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        import pymupdf as fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "Sample medical report text.")
        tmp.write(doc.tobytes())
        tmp_path = tmp.name

    original_async_session_local = AsyncSessionLocal
    session_instances = []

    def session_factory():
        sess = original_async_session_local()
        session_instances.append(sess)
        return sess

    from langchain_core.documents import Document as LCDocument
    from unittest.mock import AsyncMock

    mock_docs = [
        LCDocument(
            page_content="Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 14.2 g/dL (ref 12.0 - 15.5) Normal. Glucose: 95 mg/dL (ref 70 - 99) Normal. Platelet count 250000 /uL.",
            metadata={"type": "lab_report", "page": 1}
        )
    ]

    with (
        patch("app.db.database.AsyncSessionLocal", side_effect=session_factory),
        patch("app.api.v1.endpoints.upload.extract_text_from_file", new=AsyncMock(return_value=mock_docs)),
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
    ):
        await process_upload_background(
            job_id=job_id,
            tmp_path=tmp_path,
            filename="sample.pdf",
            user_id=user_id,
        )

    # Assert background task called AsyncSessionLocal to instantiate its own session
    assert len(session_instances) >= 1
    job = await get_job(job_id)
    assert job["status"] == UploadStatus.COMPLETED
    assert job["document_id"] is not None
    assert not os.path.exists(tmp_path)
