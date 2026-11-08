import uuid
import copy
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from tests.conftest import TEST_PASSWORD
from app.services.clinical_units import (
    parse_report_chronology,
    canonical_biomarker_key,
    compute_biomarker_delta,
    convert_to_standard,
)
from app.api.v1.endpoints.metrics import _status_from_range


def test_canonical_biomarker_key_collision_rules():
    """Verify regex whole-word matching prevents substring collisions."""
    # 1. HbA1c vs Hemoglobin
    assert canonical_biomarker_key("HbA1c") == "hba1c"
    assert canonical_biomarker_key("Glycated Hemoglobin") == "hba1c"
    assert canonical_biomarker_key("Hemoglobin A1c") == "hba1c"
    assert canonical_biomarker_key("Hemoglobin") == "hemoglobin"
    assert canonical_biomarker_key("Hb") == "hemoglobin"
    assert canonical_biomarker_key("HGB") == "hemoglobin"

    # 2. Fasting Glucose vs AST
    assert canonical_biomarker_key("Fasting Plasma Glucose") == "fasting_glucose"
    assert canonical_biomarker_key("Fasting Blood Sugar") == "fasting_glucose"
    assert canonical_biomarker_key("Glucose") == "glucose"
    assert canonical_biomarker_key("AST") == "ast"
    assert canonical_biomarker_key("Aspartate Aminotransferase") == "ast"
    assert canonical_biomarker_key("AST (SGOT)") == "ast"
    # Ensure 'fasting' NEVER matches 'ast'
    assert canonical_biomarker_key("Fasting") != "ast"

    # 3. ALT, Vit D, B12, Ferritin, Creatinine, eGFR, BUN, Uric Acid
    assert canonical_biomarker_key("Alanine Aminotransferase") == "alt"
    assert canonical_biomarker_key("ALT (SGPT)") == "alt"
    assert canonical_biomarker_key("25-OH Vitamin D") == "vitamin_d"
    assert canonical_biomarker_key("Vit D") == "vitamin_d"
    assert canonical_biomarker_key("Vitamin B12") == "vitamin_b12"
    assert canonical_biomarker_key("Serum Ferritin") == "ferritin"
    assert canonical_biomarker_key("Serum Creatinine") == "creatinine"
    assert canonical_biomarker_key("eGFR") == "egfr"
    assert canonical_biomarker_key("Blood Urea Nitrogen") == "bun"
    assert canonical_biomarker_key("Uric Acid") == "uric_acid"


def test_delta_alert_rules():
    """Verify that delta_alert only triggers on <= -10% drops for allowed normal biomarkers."""
    # Hemoglobin drop <= -10.0% on Normal -> Notable Drop
    _, pct_hb, alert_hb = compute_biomarker_delta("13.6", "15.4", status="Normal", canonical_key="hemoglobin")
    assert pct_hb == "-11.7%"
    assert alert_hb == "Notable Drop (-11.7%)"

    # Vit D rise +33.3% on Normal -> NOT flagged as notable or abnormal
    _, pct_d, alert_d = compute_biomarker_delta("46.0", "34.5", status="Normal", canonical_key="vitamin_d")
    assert pct_d == "+33.3%"
    assert alert_d is None

    # Vit B12 rise +50% on Normal -> NOT flagged as notable
    _, pct_b12, alert_b12 = compute_biomarker_delta("450", "300", status="Normal", canonical_key="vitamin_b12")
    assert alert_b12 is None

    # Ferritin rise +25% on Normal -> NOT flagged as notable
    _, pct_fer, alert_fer = compute_biomarker_delta("50", "40", status="Normal", canonical_key="ferritin")
    assert alert_fer is None

    # Uric Acid drop -20% on Normal -> NOT flagged as Notable Drop (not in allowed drop set)
    _, pct_ua, alert_ua = compute_biomarker_delta("5.0", "6.25", status="Normal", canonical_key="uric_acid")
    assert alert_ua is None

    # LDL drop -25% on Normal -> NOT flagged as Notable Drop
    _, pct_ldl, alert_ldl = compute_biomarker_delta("90", "120", status="Normal", canonical_key="ldl")
    assert alert_ldl is None


@pytest.mark.asyncio
async def test_metrics_chronology_and_collision():
    """
    E2E Verification Suite:
    1. Creates User A.
    2. Uploads Document 1 (collected_at='24 Oct 2026' with Hb 15.4, HbA1c 4.9, Glucose 83, AST 31, Ferritin 44.0, Vit D 34.5).
    3. Uploads Document 2 (collected_at='24 Apr 2027' with Hb 13.6, HbA1c 5.0, Glucose 85, AST 48, Ferritin 24.0, Vit D 46.0).
    4. Calls GET /users/me/documents/{doc2_id}/metrics and asserts:
       - Hb matches 15.4 (-11.7%, delta_alert == 'Notable Drop (-11.7%)'), NEVER 4.9.
       - Glucose matches 83 (+2.4%, delta_alert is None), NEVER 31.
       - Vit D matches 34.5 (+33.3%, delta_alert is None), NOT flagged as abnormal.
    5. Calls GET /users/me/documents/{doc1_id}/metrics (simulating switching back to Chat 1) and asserts:
       - Every metric on Document 1 has previous_value is None and delta_alert is None.
    6. Asserts DB persistence: doc.cached_metrics in DB ONLY stores raw extracted metrics and NEVER contains delta fields.
    """
    email = f"user_a_{uuid.uuid4().hex[:8]}@test.com"
    doc1_raw_metrics = [
        {"test": "Hemoglobin", "value": "15.4", "unit": "g/dL", "range": "13.0 - 17.0", "status": "Normal"},
        {"test": "HbA1c", "value": "4.9", "unit": "%", "range": "4.0 - 5.6", "status": "Normal"},
        {"test": "Glucose", "value": "83", "unit": "mg/dL", "range": "70 - 99", "status": "Normal"},
        {"test": "AST", "value": "31", "unit": "U/L", "range": "10 - 40", "status": "Normal"},
        {"test": "Ferritin", "value": "44.0", "unit": "ng/mL", "range": "30.0 - 400.0", "status": "Normal"},
        {"test": "Vit D", "value": "34.5", "unit": "ng/mL", "range": "30.0 - 100.0", "status": "Normal"},
    ]

    doc2_raw_metrics = [
        {"test": "Hemoglobin", "value": "13.6", "unit": "g/dL", "range": "13.0 - 17.0", "status": "Normal"},
        {"test": "HbA1c", "value": "5.0", "unit": "%", "range": "4.0 - 5.6", "status": "Normal"},
        {"test": "Glucose", "value": "85", "unit": "mg/dL", "range": "70 - 99", "status": "Normal"},
        {"test": "AST", "value": "48", "unit": "U/L", "range": "10 - 40", "status": "High"},
        {"test": "Ferritin", "value": "24.0", "unit": "ng/mL", "range": "30.0 - 400.0", "status": "Low"},
        {"test": "Vit D", "value": "46.0", "unit": "ng/mL", "range": "30.0 - 100.0", "status": "Normal"},
    ]

    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        # Document 1 (Oct 2026 Baseline)
        doc1 = Document(
            user_id=user_id,
            filename="oct_2026_report.pdf",
            title="October 2026 Baseline",
            collected_at="24 Oct 2026",
            cached_metrics=copy.deepcopy(doc1_raw_metrics),
            index_status="local_ready",
        )
        session.add(doc1)
        await session.commit()
        await session.refresh(doc1)
        doc1_id = doc1.id

        # Document 2 (Apr 2027 Follow-Up)
        doc2 = Document(
            user_id=user_id,
            filename="apr_2027_report.pdf",
            title="April 2027 Follow-Up",
            collected_at="24 Apr 2027",
            cached_metrics=copy.deepcopy(doc2_raw_metrics),
            index_status="local_ready",
        )
        session.add(doc2)
        await session.commit()
        await session.refresh(doc2)
        doc2_id = doc2.id

    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # ── 1. Call GET /users/me/documents/{doc2_id}/metrics ──
            res_doc2 = await ac.get(f"/users/me/documents/{doc2_id}/metrics", headers=headers)
            assert res_doc2.status_code == 200
            data2 = res_doc2.json()
            assert data2["prior_document_id"] == str(doc1_id)
            assert data2["prior_document_date"] == "24 Oct 2026"

            metrics_map2 = {m["test"]: m for m in data2["metrics"]}

            # Hb matches 15.4 (-11.7%, delta_alert == "Notable Drop (-11.7%)"), NEVER 4.9
            hb = metrics_map2["Hemoglobin"]
            assert hb["previous_value"] == "15.4"
            assert hb["previous_value"] != "4.9"
            assert hb["delta_pct"] == "-11.7%"
            assert hb["delta_alert"] == "Notable Drop (-11.7%)"

            # Glucose matches 83 (+2.4%, delta_alert is None), NEVER 31
            glucose = metrics_map2["Glucose"]
            assert glucose["previous_value"] == "83"
            assert glucose["previous_value"] != "31"
            assert glucose["delta_pct"] == "+2.4%"
            assert glucose["delta_alert"] is None

            # Vit D matches 34.5 (+33.3%, delta_alert is None), NOT flagged as abnormal
            vit_d = metrics_map2["Vit D"]
            assert vit_d["previous_value"] == "34.5"
            assert vit_d["delta_pct"] == "+33.3%"
            assert vit_d["delta_alert"] is None

            # HbA1c matches 4.9 (not 15.4)
            hba1c = metrics_map2["HbA1c"]
            assert hba1c["previous_value"] == "4.9"
            assert hba1c["previous_value"] != "15.4"

            # AST matches 31 (not 83)
            ast = metrics_map2["AST"]
            assert ast["previous_value"] == "31"
            assert ast["previous_value"] != "83"

            # ── 2. Call GET /users/me/documents/{doc1_id}/metrics (Simulating switching back to Chat 1) ──
            res_doc1 = await ac.get(f"/users/me/documents/{doc1_id}/metrics", headers=headers)
            assert res_doc1.status_code == 200
            data1 = res_doc1.json()
            assert data1["prior_document_id"] is None
            assert data1["prior_document_date"] is None

            for m in data1["metrics"]:
                # Document 1 is the earliest report; it must NEVER use the future report (Apr 2027) as baseline
                assert m["previous_value"] is None, f"{m['test']} incorrectly matched a future baseline"
                assert m["previous_date"] is None
                assert m["delta_abs"] is None
                assert m["delta_pct"] is None
                assert m["delta_alert"] is None

            # ── 3. Verify GET /users/me/metrics/trends ──
            trends_res = await ac.get("/users/me/metrics/trends", headers=headers)
            assert trends_res.status_code == 200
            trends_data = trends_res.json()
            assert trends_data["patient_id"] == "self"
            assert "reports" in trends_data
            assert len(trends_data["reports"]) == 2
            # Chronologically sorted oldest (Oct 2026) to newest (Apr 2027)
            assert trends_data["reports"][0]["document_id"] == str(doc1_id)
            assert trends_data["reports"][1]["document_id"] == str(doc2_id)

            assert "series" in trends_data
            series_by_key = {s["key"]: s for s in trends_data["series"]}
            assert "hemoglobin" in series_by_key
            hb_series = series_by_key["hemoglobin"]
            assert len(hb_series["points"]) == 2
            assert hb_series["points"][0]["value"] == 15.4
            assert hb_series["points"][1]["value"] == 13.6

            assert "fasting_glucose" in series_by_key or "glucose" in series_by_key
            assert "ast" in series_by_key

    # ── 4. DB Persistence Verification: DB column must ONLY contain raw extracted arrays ──
    async with AsyncSessionLocal() as check_session:
        from sqlalchemy.future import select

        res1 = await check_session.execute(select(Document).filter(Document.id == doc1_id))
        stored_doc1 = res1.scalars().first()
        res2 = await check_session.execute(select(Document).filter(Document.id == doc2_id))
        stored_doc2 = res2.scalars().first()

        for d, orig in [(stored_doc1, doc1_raw_metrics), (stored_doc2, doc2_raw_metrics)]:
            assert isinstance(d.cached_metrics, list)
            assert len(d.cached_metrics) == len(orig)
            for item in d.cached_metrics:
                # Must never contain enriched delta fields in DB
                assert "previous_value" not in item
                assert "previous_date" not in item
                assert "delta_abs" not in item
                assert "delta_pct" not in item
                assert "delta_alert" not in item
                assert "test" in item
                assert "value" in item
                assert "unit" in item
                assert "status" in item


@pytest.mark.asyncio
async def test_upload_status_stage_and_fact_attribution():
    """Verify upload status returns stage and memory facts resolve source_document_id."""
    from app.services.upload_jobs import create_job, update_job, UploadStatus
    from app.db.models import PatientFact, Chat

    email = f"user_b_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

        doc = Document(
            user_id=user_id,
            filename="source_report.pdf",
            title="Source Lab Report",
            index_status="local_ready",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

        chat = Chat(
            user_id=user_id,
            document_id=doc_id,
            role="user",
            message="What is my hemoglobin?",
        )
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        chat_id = chat.id

        fact = PatientFact(
            user_id=user_id,
            fact_type="condition",
            fact_text="Mild anemia observed",
            source_type="chat",
            source_id=str(chat_id),
            is_active=True,
        )
        session.add(fact)
        await session.commit()

        job_id = await create_job(user_id, session=session)
        await update_job(job_id, status=UploadStatus.PROCESSING, stage="extracting", session=session)

    with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Local JWT")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Verify GET /upload/status/{job_id} includes stage
            status_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
            assert status_res.status_code == 200
            s_data = status_res.json()
            assert s_data["job_id"] == job_id
            assert s_data["stage"] == "extracting"

            # 2. Verify GET /users/me/memory/facts includes source_document_id
            facts_res = await ac.get("/users/me/memory/facts", headers=headers)
            assert facts_res.status_code == 200
            facts_data = facts_res.json()
            assert len(facts_data) >= 1
            matched_fact = next(f for f in facts_data if f["fact_text"] == "Mild anemia observed")
            assert matched_fact["source_document_id"] == str(doc_id)


def test_demographic_reference_ranges_return_unknown_not_normal():
    """
    Fix 1: Reference intervals qualified by sex or age (e.g. Male/Female, Adult/Child)
    must return 'Unknown' instead of defaulting or false-matching to 'Normal'.
    """
    # Multi-gender ranges
    assert _status_from_range("8.2", "Male: 13.5-17.5; Female: 12.0-15.5") == "Unknown"
    assert _status_from_range("14.0", "Male: 13.5-17.5; Female: 12.0-15.5") == "Unknown"
    assert _status_from_range("22.0", "Adult Men: 13.0 - 18.0, Women: 12.0 - 16.0") == "Unknown"
    assert _status_from_range("4.5", "Child: 4.0 - 5.5, Adult: 4.5 - 6.0") == "Unknown"

    # Standard unambiguous ranges still derive properly
    assert _status_from_range("14.0", "12.0 - 16.0") == "Normal"
    assert _status_from_range("18.5", "12.0 - 16.0") == "High"
    assert _status_from_range("10.0", "12.0 - 16.0") == "Low"


def test_stoichiometric_unit_conversions_for_deltas():
    """
    Fix 2: Longitudinal deltas must correctly convert standard units across visits
    for Glucose, Creatinine, Cholesterol, and Triglycerides.
    """
    # 1. Glucose: 110 mg/dL current vs 6.1 mmol/L prior (~109.91 mg/dL)
    # 6.1 mmol/L * 18.018 = 109.91 mg/dL -> diff ~ +0.09 mg/dL
    conv_glu = convert_to_standard(6.1, "mmol/L", "mg/dL", "fasting_glucose")
    assert conv_glu is not None
    assert round(conv_glu, 1) == 109.9

    d_abs, d_pct, _ = compute_biomarker_delta(
        current_val_str="110",
        prev_val_str="6.1",
        status="Normal",
        unit="mg/dL",
        canonical_key="fasting_glucose",
        prev_unit="mmol/L",
    )
    assert d_abs is not None
    assert d_pct is not None
    assert d_abs == "+0.09 mg/dL" or d_abs.startswith("+0.1") or d_abs.startswith("+0.09")

    # 2. Creatinine: 1.2 mg/dL current vs 88.4 µmol/L prior (= 1.0 mg/dL)
    # 88.4 umol/L / 88.4 = 1.0 mg/dL -> diff +0.2 mg/dL (+20%)
    conv_cr = convert_to_standard(88.4, "µmol/L", "mg/dL", "creatinine")
    assert conv_cr is not None
    assert round(conv_cr, 1) == 1.0

    d_abs_cr, d_pct_cr, _ = compute_biomarker_delta(
        current_val_str="1.2",
        prev_val_str="88.4",
        status="Normal",
        unit="mg/dL",
        canonical_key="creatinine",
        prev_unit="µmol/L",
    )
    assert d_abs_cr == "+0.2 mg/dL"
    assert d_pct_cr == "+20.0%"

    # 3. Total Cholesterol: 200 mg/dL vs 5.17 mmol/L (~200 mg/dL)
    conv_chol = convert_to_standard(5.17, "mmol/L", "mg/dL", "cholesterol")
    assert conv_chol is not None
    assert round(conv_chol, 0) == 200.0

    # 4. Triglycerides: 150 mg/dL vs 1.69 mmol/L (~150 mg/dL)
    conv_tg = convert_to_standard(1.69, "mmol/L", "mg/dL", "triglycerides")
    assert conv_tg is not None
    assert round(conv_tg, 0) == 150.0


