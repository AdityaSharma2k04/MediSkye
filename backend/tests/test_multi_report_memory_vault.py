import uuid
import json
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, PatientFact, Chat
from app.services.fact_extractor import extract_facts
from app.services.fact_persistence import (
    save_facts,
    process_chat_memory_extraction,
    process_document_memory_extraction,
)
from tests.conftest import TEST_PASSWORD


class FakeEmbedder:
    """Fully offline deterministic embedder for tests, assigning distinct vectors to distinct texts."""
    def embed_documents(self, texts):
        results = []
        for t in texts:
            h = abs(hash(t)) % 768
            vec = [0.01] * 768
            vec[h] = 1.0
            results.append(vec)
        return results

    def embed_query(self, text):
        h = abs(hash(text)) % 768
        vec = [0.01] * 768
        vec[h] = 1.0
        return vec

    async def aembed_documents(self, texts):
        return self.embed_documents(texts)

    async def aembed_query(self, text):
        return self.embed_query(text)


@pytest.mark.asyncio
async def test_three_consecutive_reports_uploaded_and_queried():
    """
    Test 1: Simulate a user with memory_consent_granted=True uploading & querying
    3 distinct reports in sequence (CBC/Iron, Lipid/Metabolic, Thyroid/Vitamin).
    Assert that facts from all 3 reports (3/3) are extracted, persisted in patient_facts,
    and returned by GET /users/me/memory/facts with proper source report provenance.
    """
    email = f"three_reports_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            memory_consent_granted=True,
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Create 3 distinct medical reports
        doc1 = Document(
            user_id=user.id,
            filename="cbc_iron_panel.pdf",
            title="CBC & Iron Panel",
            index_status="synced",
            cached_metrics=[
                {"test": "Haemoglobin", "value": "10.5", "unit": "g/dL", "range": "13.0 - 17.0", "status": "Low"},
                {"test": "Serum Ferritin", "value": "12", "unit": "ng/mL", "range": "30 - 400", "status": "Low"},
            ],
        )
        doc2 = Document(
            user_id=user.id,
            filename="lipid_metabolic_panel.pdf",
            title="Lipid & Metabolic Panel",
            index_status="synced",
            cached_metrics=[
                {"test": "Total Cholesterol", "value": "235", "unit": "mg/dL", "range": "< 200", "status": "High"},
                {"test": "Fasting Plasma Glucose", "value": "145", "unit": "mg/dL", "range": "70 - 99", "status": "High"},
            ],
        )
        doc3 = Document(
            user_id=user.id,
            filename="thyroid_vitamin_panel.pdf",
            title="Thyroid & Vitamin Panel",
            index_status="synced",
            cached_metrics=[
                {"test": "TSH", "value": "6.5", "unit": "µIU/mL", "range": "0.40 - 4.20", "status": "High"},
                {"test": "Vitamin D", "value": "18", "unit": "ng/mL", "range": "30 - 100", "status": "Low"},
            ],
        )
        session.add_all([doc1, doc2, doc3])
        await session.commit()
        await session.refresh(doc1)
        await session.refresh(doc2)
        await session.refresh(doc3)

    # Responses returned during extraction for each report
    report_responses = {
        "cbc_iron_panel.pdf": json.dumps({
            "facts": [
                {"type": "measurement", "text": "Haemoglobin: 10.5 g/dL (Low)", "confidence": 0.95},
                {"type": "measurement", "text": "Serum Ferritin: 12 ng/mL (Low)", "confidence": 0.95},
                {"type": "condition", "text": "Iron deficiency anemia", "confidence": 0.90},
            ],
            "retractions": [],
        }),
        "lipid_metabolic_panel.pdf": json.dumps({
            "facts": [
                {"type": "measurement", "text": "Total Cholesterol: 235 mg/dL (High)", "confidence": 0.95},
                {"type": "measurement", "text": "Fasting Plasma Glucose: 145 mg/dL (High)", "confidence": 0.95},
                {"type": "condition", "text": "Hypercholesterolemia", "confidence": 0.90},
            ],
            "retractions": [],
        }),
        "thyroid_vitamin_panel.pdf": json.dumps({
            "facts": [
                {"type": "measurement", "text": "TSH: 6.5 µIU/mL (High)", "confidence": 0.95},
                {"type": "measurement", "text": "Vitamin D: 18 ng/mL (Low)", "confidence": 0.95},
                {"type": "condition", "text": "Subclinical hypothyroidism", "confidence": 0.85},
            ],
            "retractions": [],
        }),
    }

    mock_client = MagicMock()

    def mock_generate_content(model=None, contents=None, config=None):
        mock_resp = MagicMock()
        text_str = str(contents)
        matched_json = None
        for doc_name, resp_json in report_responses.items():
            if f'document="{doc_name}"' in text_str or f"Lab Report: {doc_name}" in text_str:
                matched_json = resp_json
                break
        if not matched_json:
            matched_json = report_responses["cbc_iron_panel.pdf"]
        mock_resp.text = matched_json
        return mock_resp

    mock_client.models.generate_content.side_effect = mock_generate_content

    with patch("google.genai.Client", return_value=mock_client), \
         patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()):

        # Execute document memory extraction for all 3 reports consecutively
        res1 = await process_document_memory_extraction(doc_id=doc1.id, user_id=user.id)
        assert res1["inserted"] == 3

        res2 = await process_document_memory_extraction(doc_id=doc2.id, user_id=user.id)
        assert res2["inserted"] == 3

        res3 = await process_document_memory_extraction(doc_id=doc3.id, user_id=user.id)
        assert res3["inserted"] == 3

        # Query GET /users/me/memory/facts via authenticated API
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            facts_res = await ac.get("/users/me/memory/facts", headers=headers)
            assert facts_res.status_code == 200
            facts_list = facts_res.json()

            # Verify facts from all 3 reports (9 total: 3 per report) are present and active
            assert len(facts_list) == 9

            # Check provenance linking back to each document
            source_doc_ids = {f.get("source_document_id") for f in facts_list if f.get("source_document_id")}
            assert str(doc1.id) in source_doc_ids
            assert str(doc2.id) in source_doc_ids
            assert str(doc3.id) in source_doc_ids

            # Verify report 1 analytes
            assert any("haemoglobin" in f["fact_text"].lower() for f in facts_list)
            assert any("ferritin" in f["fact_text"].lower() for f in facts_list)

            # Verify report 2 analytes
            assert any("cholesterol" in f["fact_text"].lower() for f in facts_list)
            assert any("glucose" in f["fact_text"].lower() for f in facts_list)

            # Verify report 3 analytes
            assert any("tsh" in f["fact_text"].lower() for f in facts_list)
            assert any("vitamin d" in f["fact_text"].lower() for f in facts_list)


@pytest.mark.asyncio
async def test_transient_gemini_failure_and_rate_limit_recovery():
    """
    Test 2: Simulate Report 2 hitting a transient 429 Resource Exhausted on Attempt 1,
    and returning markdown-fenced JSON array on Attempt 2 with backup model.
    Assert that extract_facts catches 429, falls back, strips markdown fences,
    normalizes synonyms (lab_result -> measurement), defaults confidence, and succeeds 100%.
    """
    attempt_count = 0

    def mock_flaky_generate(model=None, contents=None, config=None):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise Exception("429 Resource Exhausted: rate limit exceeded in burst")

        mock_resp = MagicMock()
        # Returns markdown-fenced list with category synonyms and missing confidence
        mock_resp.text = """```json
[
  {"type": "lab_result", "text": "Total Cholesterol: 235 mg/dL (High)"},
  {"type": "vital", "text": "Fasting Plasma Glucose: 145 mg/dL (High)"},
  {"type": "diagnosis", "text": "Metabolic syndrome", "confidence": 0.9}
]
```"""
        return mock_resp

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = mock_flaky_generate

    with patch("google.genai.Client", return_value=mock_client), \
         patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()):

        user_id = uuid.uuid4()
        messages = [
            {"role": "user", "content": "Doctor, here are my lipid results."},
            {"role": "assistant", "content": "Your cholesterol is 235 mg/dL and glucose is 145 mg/dL."},
        ]

        result = await extract_facts(
            messages=messages,
            existing_facts=[],
            user_id=user_id,
            document_name="lipid_panel.pdf",
            backoff_delays=[0.01, 0.01, 0.01, 0.01],
        )

        # Assert attempt 1 failed and attempt 2 succeeded
        assert attempt_count >= 2
        assert len(result["facts"]) == 3

        # Verify category synonym normalization
        assert result["facts"][0]["type"] == "measurement"
        assert result["facts"][0]["confidence"] == 0.85  # Defaulted from missing
        assert "Total Cholesterol: 235 mg/dL" in result["facts"][0]["text"]

        assert result["facts"][1]["type"] == "measurement"  # "vital" -> "measurement"
        assert "Fasting Plasma Glucose: 145 mg/dL" in result["facts"][1]["text"]

        assert result["facts"][2]["type"] == "condition"  # "diagnosis" -> "condition"
        assert result["facts"][2]["text"] == "Metabolic syndrome"


@pytest.mark.asyncio
async def test_upload_time_memory_extraction():
    """
    Test 3: Verify that when a user with memory_consent_granted=True uploads a report,
    process_document_memory_extraction persists key findings to patient_facts
    even before any chat message is sent.
    """
    email = f"upload_mem_{uuid.uuid4().hex[:8]}@example.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            memory_consent_granted=True,
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            user_id=user.id,
            filename="comprehensive_metabolic_panel.pdf",
            title="Comprehensive Metabolic Panel",
            index_status="synced",
            cached_metrics=[
                {"test": "Serum Creatinine", "value": "1.8", "unit": "mg/dL", "range": "0.7 - 1.3", "status": "High"},
                {"test": "eGFR", "value": "38", "unit": "mL/min/1.73m²", "range": "> 60", "status": "Low"},
                {"test": "Potassium", "value": "5.3", "unit": "mmol/L", "range": "3.5 - 5.1", "status": "High"},
            ],
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "facts": [
            {"type": "measurement", "text": "Serum Creatinine: 1.8 mg/dL (High)", "confidence": 0.95},
            {"type": "measurement", "text": "eGFR: 38 mL/min/1.73m² (Low)", "confidence": 0.95},
            {"type": "measurement", "text": "Potassium: 5.3 mmol/L (High)", "confidence": 0.95},
        ],
        "retractions": [],
    })

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client), \
         patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()):

        # Execute upload-time extraction
        stats = await process_document_memory_extraction(doc_id=doc.id, user_id=user.id)
        assert stats["inserted"] == 3

        # Verify facts exist in DB linked to source_type="document" and source_id=str(doc.id)
        async with AsyncSessionLocal() as session:
            facts_res = await session.execute(
                select(PatientFact).filter(
                    PatientFact.user_id == user.id,
                    PatientFact.is_active.is_(True),
                )
            )
            saved_facts = facts_res.scalars().all()
            assert len(saved_facts) == 3

            for f in saved_facts:
                assert f.source_type == "document"
                assert f.source_id == str(doc.id)
                assert "[Source Report: comprehensive_metabolic_panel.pdf]" in f.fact_text

            # Verify GET /users/me/memory/facts returns them with source_document_id populated
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
                token = login_res.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                api_facts = await ac.get("/users/me/memory/facts", headers=headers)
                assert api_facts.status_code == 200
                fact_items = api_facts.json()
                assert len(fact_items) == 3
                for item in fact_items:
                    assert item["source_document_id"] == str(doc.id)
