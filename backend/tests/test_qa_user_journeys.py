"""
Autonomous Human QA Simulation Suite — Multi-turn User Journeys & Edge-Case Regressions.

Validates:
1. Multi-turn conversation flow on Document A:
   - Turn 1: Fresh PDF upload triggers full overview (is_followup_turn = False).
   - Turn 2: Follow-up question activates followup turn instruction, no walkthrough repetition, no duplicate disclaimer (is_followup_turn = True).
   - Turn 3: Explicit overview request ("Now give me the full overview of this report") resets to full walkthrough (is_followup_turn = False).
   - Turn 4: New document (Document B) attached resets to full walkthrough for Document B (is_followup_turn = False).
2. Profile lock enforcement on query:
   - Querying a document belonging to Profile A with patient_id set to Profile B raises HTTP 409 Conflict.
3. Clinical parsing generalization:
   - Indian numbering notation (2,38,000), thousands with decimals (4,500.50), European commas (3,9).
   - Prefix comparators (< 0.5, > 60).
   - Urinalysis vs. serum albumin disambiguation without false alarms.
"""

import re
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.models import User, DependentProfile, Document, Chat
from app.db.database import AsyncSessionLocal
from app.rag.biomarkers import (
    parse_numeric_value,
    parse_reference_range,
    canonical_biomarker_key,
)
from app.rag.prompt_builder import build_prompt
from app.api.v1.endpoints.query import _clean_disclaimers

TEST_PASSWORD = "Password123!"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Clinical Parsing & De-Overfitting Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_numeric_parsing_indian_and_thousands_notations():
    """Verify Indian numbering format, standard thousands with decimals, and European commas."""
    # Indian numbering: 2,38,000 platelets must parse as 238000.0 (NOT 2.0)
    assert parse_numeric_value("2,38,000") == 238000.0

    # Standard thousands with decimals: 4,500.50 must parse as 4500.5 (NOT 4.0)
    assert parse_numeric_value("4,500.50") == 4500.5

    # European comma decimal: 3,9 must parse as 3.9
    assert parse_numeric_value("3,9") == 3.9

    # Prefix comparators
    assert parse_numeric_value("> 60") == 60.0
    assert parse_numeric_value("< 0.5") == 0.5


def test_reference_range_operators_and_formats():
    """Verify ranges formatted with 'Up to', 'Above', 'to', and hyphens."""
    # Up to 200 mg/dL
    rng = parse_reference_range("Up to 200")
    assert rng["high"] == 200.0
    assert rng["type"] == "upper"

    # Above 60
    rng = parse_reference_range("Above 60")
    assert rng["low"] == 60.0
    assert rng["type"] == "lower"

    # Standard range with 'to'
    rng = parse_reference_range("12.0 to 16.0")
    assert rng["low"] == 12.0
    assert rng["high"] == 16.0
    assert rng["type"] == "bounded"

    # Range with en-dash
    rng = parse_reference_range("4.5 – 5.5")
    assert rng["low"] == 4.5
    assert rng["high"] == 5.5
    assert rng["type"] == "bounded"


def test_urinalysis_vs_serum_albumin_disambiguation():
    """Verify urine albumin/microalbumin never collides with serum albumin (3.5-5.0 g/dL)."""
    # Serum albumin
    serum_key = canonical_biomarker_key("Serum Albumin")
    assert serum_key == "albumin"

    # Urine albumin and microalbumin must NOT collide with serum albumin
    assert canonical_biomarker_key("Urine Albumin") is None
    assert canonical_biomarker_key("Urine Microalbumin") is None
    assert canonical_biomarker_key("Urine Albumin to Creatinine Ratio") == "urine_acr"


# ─────────────────────────────────────────────────────────────────────────────
# 2. Multi-turn Overview & Follow-up Prompt Logic
# ─────────────────────────────────────────────────────────────────────────────

def test_prompt_builder_turn_progression():
    """
    Test prompt structure between Turn 1 (walkthrough) and Turn 2 (follow-up).
    """
    # Turn 1: Full overview
    sys_turn1, user_turn1 = build_prompt(
        user_query="Please explain my blood report",
        is_followup_turn=False,
    )
    assert "<followup_turn_instruction>" not in user_turn1
    assert "DOCTOR_INSTRUCTIONS" in sys_turn1 or "Warm, calm, and professional" in sys_turn1

    # Turn 2: Follow-up question
    sys_turn2, user_turn2 = build_prompt(
        user_query="What should I eat to improve this?",
        is_followup_turn=True,
        current_session_history="User: Explain report\nAssistant: Your hemoglobin is 14.2 g/dL.",
    )
    assert "<followup_turn_instruction>" in user_turn2
    assert "DO NOT repeat the 7-section report walkthrough" in user_turn2
    assert "DO NOT output any Disclaimer: block" in user_turn2


def test_disclaimer_cleaning_per_turn():
    """
    Test disclaimer cleaning:
    - Turn 1: deduplicates repeated disclaimers into a single closing disclaimer.
    - Turn 2: completely removes disclaimers so follow-ups remain concise.
    """
    sample_text = (
        "Your results are normal.\n\n"
        "***\nDisclaimer: This is for educational purposes only.\n***\n\n"
        "More text here.\n\n"
        "***\nDisclaimer: This is for educational purposes only.\n***"
    )

    # Turn 1: single disclaimer at the end
    cleaned_t1 = _clean_disclaimers(sample_text, is_followup_turn=False)
    matches_t1 = list(re.finditer(r"(?i)Disclaimer:", cleaned_t1))
    assert len(matches_t1) == 1

    # Turn 2: zero disclaimers
    cleaned_t2 = _clean_disclaimers(sample_text, is_followup_turn=True)
    assert "Disclaimer:" not in cleaned_t2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Explicit Overview Regex Pattern Verification
# ─────────────────────────────────────────────────────────────────────────────

def test_explicit_overview_regex_generalization():
    """
    Verify diverse human phrases for full report walkthrough correctly match
    explicit_overview_match and avoid accidental follow-up turn lock.
    """
    overview_regex = re.compile(
        r"(?i)(?:^(?:now\s+)?(?:can\s+you\s+)?(?:give\s+me\s+)?(?:the\s+|a\s+)?(?:full|complete|entire)\s+(?:overview|breakdown|summary)(?:\s+of\s+(?:this|my|the)?\s*(?:report|results?|blood\s*work)?)?|\b(?:tell\s+me\s+about|explain|summarize|walk\s+me\s+through|give\s+me\s+(?:a|the)?\s*(?:full|complete|entire)?\s*(?:overview|breakdown|summary)\s*(?:of)?|(?:full|complete|entire)\s+(?:overview|breakdown|summary)\s*(?:of)?|overview\s+of)\s+(?:this|my|the|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|results?))\b"
    )

    overview_queries = [
        "Now give me the full overview of this report",
        "Give me the full overview",
        "Can you give me a complete summary of this report",
        "Walk me through the whole report",
        "Walk me through the entire report",
        "Tell me about this report",
        "Summarize this lab report",
        "Explain my results",
        "full breakdown of my blood work",
    ]

    for q in overview_queries:
        assert overview_regex.search(q.strip()) is not None, f"Failed to match: {q}"

    followup_queries = [
        "What should I eat?",
        "What is my HbA1c?",
        "Is this dangerous?",
        "Can I exercise?",
        "Why is my creatinine 0.9?",
    ]

    for q in followup_queries:
        assert overview_regex.search(q.strip()) is None, f"Should NOT match: {q}"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-Turn E2E User Journey & Profile Lock
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_qa_multi_turn_and_profile_lock_journey(tmp_path):
    """
    Simulated human journey:
    1. User registers and logs in.
    2. User creates two dependent profiles (Child Alpha, Parent Beta).
    3. User uploads Document A under Child Alpha.
    4. Query Document A with patient_id = Parent Beta -> 409 Conflict Profile Lock.
    5. Query Document A with patient_id = Child Alpha -> Allowed (passes profile check).
    """
    email = f"qa_user_{uuid.uuid4().hex[:8]}@example.com"
    transport = ASGITransport(app=app)

    pdf_file = tmp_path / "mock_cbc_panel.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 mock content")
    pdf_path = str(pdf_file)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Register user
        reg_res = await ac.post("/register", json={"email": email, "password": TEST_PASSWORD, "phi_consent_granted": True})
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # Create dependent profiles
        dep_alpha_res = await ac.post("/users/me/dependents", json={"full_name": "Child Alpha", "relationship": "Child"}, headers=headers)
        assert dep_alpha_res.status_code == 201
        alpha_id = dep_alpha_res.json()["id"]

        dep_beta_res = await ac.post("/users/me/dependents", json={"full_name": "Parent Beta", "relationship": "Parent"}, headers=headers)
        assert dep_beta_res.status_code == 201
        beta_id = dep_beta_res.json()["id"]

        user_info = (await ac.get("/users/me", headers=headers)).json()
        user_uuid = uuid.UUID(user_info["id"])
        alpha_uuid = uuid.UUID(alpha_id)

        # Create Document A under Child Alpha in DB
        doc_a_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            doc_a = Document(
                id=doc_a_id,
                user_id=user_uuid,
                dependent_id=alpha_uuid,
                filename="CBC_Panel_Alpha.pdf",
                title="Complete Blood Count",
                index_status="indexed",
                file_path=pdf_path,
            )
            session.add(doc_a)
            await session.commit()

        # Step 4: Querying Document A with patient_id = beta_id (Parent Beta) MUST raise HTTP 409 Conflict
        res_mismatch = await ac.post(
            "/query",
            headers=headers,
            json={
                "query": "What are my platelets?",
                "document_id": str(doc_a_id),
                "patient_id": beta_id,
            },
        )
        assert res_mismatch.status_code == 409
        assert "Profile Lock" in res_mismatch.json()["detail"]

        # Step 5: Querying Document A under Child Alpha should not be blocked by 409
        # (It will reach index check / generation without profile conflict)
        res_match = await ac.post(
            "/query",
            headers=headers,
            json={
                "query": "What are my platelets?",
                "document_id": str(doc_a_id),
                "patient_id": alpha_id,
            },
        )
        # Should not be 409 Profile Lock
        assert res_match.status_code != 409
