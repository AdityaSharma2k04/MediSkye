import io
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.models import User, DependentProfile
from app.api.v1.endpoints.upload import _extract_printed_patient_name, _tokenize_name

TEST_PASSWORD = "Password123!"


def test_extract_printed_patient_name_patterns():
    # Various real-world clinical report header formats
    t1 = "Patient Name : Mr. HARISH MENON\nAge: 45 Y / Male\nRef By: Dr. Sharma\n"
    assert _extract_printed_patient_name(t1) == "HARISH MENON"

    t2 = "PATIENT'S NAME: Mrs. Anjali Verma\nDOB: 12/04/1982\n"
    assert _extract_printed_patient_name(t2) == "Anjali Verma"

    t3 = "Pt. Name : Dr. Rajesh Rao   Age/Gender: 52/M"
    assert _extract_printed_patient_name(t3) == "Rajesh Rao"

    t4 = "General Laboratory Report\nNo patient specified\nGlucose: 95 mg/dL"
    assert _extract_printed_patient_name(t4) is None

    tokens_menon = _tokenize_name("Mr. HARISH MENON")
    assert "harish" in tokens_menon
    assert "menon" in tokens_menon
    assert "mr" not in tokens_menon


@pytest.mark.asyncio
async def test_upload_pdf_printed_name_mismatch_raises_409():
    """
    Uploading a PDF with printed name 'Mr. HARISH MENON' while dependent 'Anjali Verma'
    is selected raises HTTP 409 Profile Lock.
    """
    email = f"profile_lock_{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user
        reg_res = await ac.post("/register", json={"email": email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create two dependent profiles: Anjali Verma and Harish Menon
        dep1_res = await ac.post("/users/me/dependents", json={"full_name": "Anjali Verma", "relationship": "Sister"}, headers=headers)
        assert dep1_res.status_code == 201
        anjali_id = dep1_res.json()["id"]

        dep2_res = await ac.post("/users/me/dependents", json={"full_name": "Harish Menon", "relationship": "Father"}, headers=headers)
        assert dep2_res.status_code == 201
        harish_id = dep2_res.json()["id"]

        # Generate simple PDF containing text "Patient Name: Mr. HARISH MENON"
        import pymupdf as fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), "METROPOLIS HEALTHCARE LAB REPORT\nPatient Name: Mr. HARISH MENON\nAge: 58 Y / Male\nHemoglobin: 14.2 g/dL\n")
        pdf_bytes = doc.tobytes()
        doc.close()

        # 1. Upload under Anjali Verma -> Must raise HTTP 409 Profile Lock
        files = {"file": ("menon_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data = {"patient_id": anjali_id}
        res_mismatch = await ac.post("/upload", files=files, data=data, headers=headers)
        assert res_mismatch.status_code == 409
        detail = res_mismatch.json()["detail"]
        assert "Profile Lock" in detail
        assert "HARISH MENON" in detail
        assert "Anjali Verma" in detail

        # 2. Upload under Harish Menon -> Must succeed (202 Accepted)
        files_ok = {"file": ("menon_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data_ok = {"patient_id": harish_id}
        res_ok = await ac.post("/upload", files=files_ok, data=data_ok, headers=headers)
        assert res_ok.status_code == 202
        assert "job_id" in res_ok.json()
