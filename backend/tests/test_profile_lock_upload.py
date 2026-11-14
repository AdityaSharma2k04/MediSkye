import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.models import User, DependentProfile, Document, Chat
from app.db.database import AsyncSessionLocal

TEST_PASSWORD = "Password123!"


@pytest.mark.asyncio
async def test_upload_pdf_succeeds_without_printed_name_block():
    """
    Uploading a PDF with any clinical/lab report text succeeds (202 Accepted)
    under the selected profile without false-positive 409 blocks on upload.
    """
    email = f"profile_upload_{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user
        reg_res = await ac.post("/register", json={"email": email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create two dependent profiles
        dep1_res = await ac.post("/users/me/dependents", json={"full_name": "Jordan Lee", "relationship": "Sister"}, headers=headers)
        assert dep1_res.status_code == 201
        jordan_id = dep1_res.json()["id"]

        dep2_res = await ac.post("/users/me/dependents", json={"full_name": "Taylor Smith", "relationship": "Father"}, headers=headers)
        assert dep2_res.status_code == 201
        taylor_id = dep2_res.json()["id"]

        # Generate simple PDF
        import pymupdf as fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "METROPOLIS HEALTHCARE LAB REPORT\nPatient Name: Sample Patient\nAge: 48 Y / Male\nHemoglobin: 14.2 g/dL\n")
        pdf_bytes = doc.tobytes()
        doc.close()

        # Upload under Jordan Lee -> Must succeed without printed-name blocker (202 Accepted)
        files = {"file": ("sample_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data = {"patient_id": jordan_id}
        res_upload = await ac.post("/upload", files=files, data=data, headers=headers)
        assert res_upload.status_code == 202
        assert "job_id" in res_upload.json()


@pytest.mark.asyncio
async def test_cross_profile_query_and_reassign_lock():
    """
    Strict post-upload profile lock:
    1. Querying a report from a different profile raises HTTP 409 Profile Lock.
    2. Attempting to reassign document profile via PATCH /users/me/documents/{id}/patient raises 403 Forbidden.
    """
    email = f"profile_lock_query_{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user
        reg_res = await ac.post("/register", json={"email": email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create dependent profiles
        dep1_res = await ac.post("/users/me/dependents", json={"full_name": "Profile Alpha", "relationship": "Child"}, headers=headers)
        alpha_id = dep1_res.json()["id"]
        dep2_res = await ac.post("/users/me/dependents", json={"full_name": "Profile Beta", "relationship": "Spouse"}, headers=headers)
        beta_id = dep2_res.json()["id"]

        user_info = (await ac.get("/users/me", headers=headers)).json()
        user_id = uuid.UUID(user_info["id"])
        alpha_uuid = uuid.UUID(alpha_id)

        # Create document under Profile Alpha
        doc_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            doc = Document(id=doc_id, user_id=user_id, dependent_id=alpha_uuid, filename="cbc_panel.pdf", title="CBC Panel")
            session.add(doc)
            await session.commit()

        # 1. Attempt to reassign document patient -> 403 Forbidden
        patch_res = await ac.patch(
            f"/users/me/documents/{doc_id}/patient",
            headers=headers,
            json={"patient_id": beta_id},
        )
        assert patch_res.status_code == 403
        assert "permanently locked" in patch_res.json()["detail"]

        # 2. Query document with patient_id=beta_id (cross-profile) -> 409 Profile Lock
        query_res = await ac.post(
            "/query",
            headers=headers,
            json={
                "query": "What is my hemoglobin?",
                "document_id": str(doc_id),
                "patient_id": beta_id,
            },
        )
        assert query_res.status_code == 409
        assert "Profile Lock" in query_res.json()["detail"]
