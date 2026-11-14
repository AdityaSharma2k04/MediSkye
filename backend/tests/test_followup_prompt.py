import pytest
import re
from app.rag.prompt_builder import (
    build_prompt,
    REPORT_WALKTHROUGH_RULES,
    COMPARISON_RULES,
)
from app.rag.safety import append_disclaimer


def is_explicit_overview_request(query_text: str) -> bool:
    """Helper reproducing the regex / logic used in query.py for explicit walkthrough requests."""
    # This should match full report overview requests, but NOT focused biomarker follow-ups
    # like "why is my bilirubin high?" or "what about my platelets?"
    from app.api.v1.endpoints.query import is_explicit_overview_query  # If exposed, or check regex directly
    return is_explicit_overview_query(query_text)


def test_1_build_prompt_followup_turn_system_instruction():
    """
    Test 1: build_prompt(..., is_followup_turn=True) produces a system prompt containing
    FOLLOWUP_TURN_RULES and NOT containing REPORT_WALKTHROUGH_RULES or COMPARISON_RULES.
    Currently FAILS because build_prompt unconditionally injects DOCTOR_INSTRUCTIONS.
    """
    from app.rag.prompt_builder import FOLLOWUP_TURN_RULES

    system_prompt, user_content = build_prompt(
        user_query="Why is my ferritin low?",
        is_followup_turn=True,
    )

    assert FOLLOWUP_TURN_RULES in system_prompt, "System prompt must contain FOLLOWUP_TURN_RULES on follow-up turn"
    assert "### 🟢 The Short Version" not in system_prompt, "System prompt must NOT contain REPORT_WALKTHROUGH_RULES on follow-up turn"
    assert "LONGITUDINAL COMPARISONS" not in system_prompt, "System prompt must NOT contain COMPARISON_RULES on standard follow-up turn"


def test_2_build_prompt_initial_turn_system_instruction():
    """
    Test 2: build_prompt(..., is_followup_turn=False) produces a system prompt containing
    REPORT_WALKTHROUGH_RULES and COMPARISON_RULES.
    """
    system_prompt, user_content = build_prompt(
        user_query="Explain my new lab report",
        is_followup_turn=False,
    )

    assert "### 🟢 The Short Version" in system_prompt
    assert "LONGITUDINAL COMPARISONS" in system_prompt


def test_3_explicit_overview_match_precision():
    """
    Test 3: Negative and positive checks on explicit overview detection.
    Questions like 'why is my bilirubin high?' or 'what about my platelets?'
    must NOT match as an explicit walkthrough request.
    Only queries like 'walk me through my report', 'explain my lab results', 'summarize my report' match.
    """
    # Import the function from query or prompt_builder
    try:
        from app.api.v1.endpoints.query import is_explicit_overview_query
    except ImportError:
        pytest.fail("is_explicit_overview_query helper must exist in query.py")

    # Negative cases (should be False)
    assert not is_explicit_overview_query("why is my bilirubin high?")
    assert not is_explicit_overview_query("what about my platelets?")
    assert not is_explicit_overview_query("can you explain why my glucose is elevated?")
    assert not is_explicit_overview_query("should I be worried about my creatinine?")
    assert not is_explicit_overview_query("is 14.2 good for hemoglobin?")
    assert not is_explicit_overview_query("tell me about my ferritin")
    assert not is_explicit_overview_query("what should i do in order to fix my health")
    assert not is_explicit_overview_query("how do i improve my ferritin")
    assert not is_explicit_overview_query("is this serious")
    assert not is_explicit_overview_query("what does this mean for me")

    # Positive cases (should be True)
    assert is_explicit_overview_query("walk me through my report")
    assert is_explicit_overview_query("explain my lab results")
    assert is_explicit_overview_query("summarize my report")
    assert is_explicit_overview_query("give me a full breakdown of my results")
    assert is_explicit_overview_query("give me an overview of my lab report")
    assert is_explicit_overview_query("tell me about this report")
    assert is_explicit_overview_query("now give me the full overview")


def test_followup_logging_caplog(caplog):
    """
    Test 3b: Exactly one logger.info per request with session id, document id,
    the boolean and the reason, and no query text.
    """
    import logging
    from app.api.v1.endpoints.query import logger as query_logger, compute_followup_turn_context

    with caplog.at_level(logging.INFO, logger="app.api.v1.endpoints.query"):
        caplog.clear()
        is_followup, reason = compute_followup_turn_context(
            has_walked_through=True,
            query_text="what about my iron?",
            session_id="sess-123",
            document_id="doc-456",
        )
        assert is_followup is True
        info_records = [r for r in caplog.records if r.levelno == logging.INFO and "sess-123" in r.message]
        assert len(info_records) == 1
        msg = info_records[0].message
        assert "doc-456" in msg
        assert "is_followup_turn=True" in msg or "True" in msg
        assert "what about my iron" not in msg  # No query text in log!


def test_4_history_condensing():
    """
    Test 4: History condenser (prompt_builder.py:condense_chat_history)
    - Strips ### headings, markdown table rows, JSON code blocks, and disclaimers.
    - Caps assistant text at <= 350 chars at sentence end.
    - Appends stub '[Full report walkthrough and comparison table already provided earlier in this conversation.]'
      if original contained 'The Short Version' or >=6 table rows.
    - User text capped at 500 chars.
    - Last 6 turns (12 messages) considered.
    - Empty input returns "".
    """
    from app.rag.prompt_builder import condense_chat_history

    # Empty check
    assert condense_chat_history([]) == ""
    assert condense_chat_history(None) == ""

    # Synthetic walkthrough turn
    ten_row_table = "\n".join([f"| Marker{i} | 10{i} | High |" for i in range(10)])
    walkthrough_ai = (
        "### 🟢 The Short Version\n"
        "All markers are generally stable. Your blood count shows healthy cellular parameters.\n\n"
        "### Complete Blood Count\n"
        "- Hemoglobin: 14.5 g/dL (Normal)\n"
        "- Platelets: 250,000 /mcL (Normal)\n\n"
        f"| Biomarker | Value | Status |\n|---|---|---|\n{ten_row_table}\n\n"
        "```json\n"
        '{"abnormal_flags": []}\n'
        "```\n\n"
        "**Disclaimer:** This explanation is for educational purposes only."
    )

    long_user_query = "What about my markers? " + ("detail " * 120)
    chats = [
        {"role": "user", "message": long_user_query},
        {"role": "ai", "message": walkthrough_ai},
    ]

    condensed = condense_chat_history(chats)

    assert "###" not in condensed
    assert "|" not in condensed
    assert "```" not in condensed
    assert "abnormal_flags" not in condensed
    assert "Disclaimer:" not in condensed
    stub = "[Full report walkthrough and comparison table already provided earlier in this conversation.]"
    assert stub in condensed

    # Assistant portion before the stub is <= 350 chars and ends on a sentence boundary
    doctor_segment = condensed.split("Doctor:")[-1]
    assistant_part = doctor_segment.replace(stub, "").strip()
    assert len(assistant_part) <= 350
    assert assistant_part.endswith((".", "!", "?"))

    # User text is capped at <= 500 chars
    user_segment = condensed.split("Doctor:")[0].replace("User:", "").strip()
    assert len(user_segment) <= 500


def test_5_safety_double_disclaimer_guard():
    """
    Test 5: Safety disclaimer detection and DECISION_2 behavior:
    - Model-written **Disclaimer:** at line start -> server does NOT append.
    - Mid-sentence 'the footer of the report says Disclaimer: ...' -> server DOES append.
    - Educational mention without a standalone disclaimer line -> server DOES append.
    - Standard follow-up turn -> server suppresses disclaimer.
    - Critical follow-up turn (has_critical_alert=True or critical wording) -> server KEEPS disclaimer.
    - Follow-up with SAFE_FALLBACK -> server KEEPS disclaimer.
    """
    from app.rag.output_filter import SAFE_FALLBACK

    # 1. Model-written disclaimer at line start
    text_with_prompt_disclaimer = (
        "Your hemoglobin is 14.5 g/dL, which is in the normal range.\n\n"
        "**Disclaimer:** This explanation is for educational purposes only and is not a substitute for "
        "professional medical advice, diagnosis, or treatment."
    )
    res_line_start = append_disclaimer(text_with_prompt_disclaimer)
    assert res_line_start.count("Disclaimer:") == 1

    # 2. Mid-sentence mentions
    text_mid_sentence = "The footer of the report says Disclaimer: for clinical reference only."
    res_mid = append_disclaimer(text_mid_sentence)
    assert "**Disclaimer:** This explanation is for educational purposes only" in res_mid

    # 3. Educational mention without disclaimer line
    text_educational = "This educational explanation should be discussed with a qualified healthcare provider."
    res_edu = append_disclaimer(text_educational)
    assert "**Disclaimer:** This explanation is for educational purposes only" in res_edu

    # 4. Standard follow-up turn: suppressed
    text_followup = "Your platelets are 250,000 /mcL, well within normal limits."
    res_followup = append_disclaimer(text_followup, is_followup_turn=True)
    assert "Disclaimer:" not in res_followup

    # 5. DECISION_2: Critical follow-up: KEEP disclaimer
    text_critical = "Your potassium is 6.8 mmol/L, which is critically high."
    res_critical = append_disclaimer(text_critical, is_followup_turn=True, has_critical_alert=True)
    assert "Disclaimer:" in res_critical

    # 6. DECISION_2: SAFE_FALLBACK follow-up: KEEP disclaimer
    res_safe_fallback = append_disclaimer(SAFE_FALLBACK, is_followup_turn=True)
    assert "Disclaimer:" in res_safe_fallback


def test_comparison_aware_followup_turn():
    """
    Test comparison-aware follow-up turns:
    - On follow-up turns, if user asks to compare / trend / vs / previous report,
      system prompt includes COMPARISON_RULES alongside FOLLOWUP_TURN_RULES.
    - If user does not ask for comparison on follow-up, COMPARISON_RULES is absent.
    - On initial turn (is_followup_turn=False), walkthrough and comparison rules are both present.
    """
    # 1. Comparison follow-up
    sys_compare, _ = build_prompt(
        user_query="compare this with my last report",
        is_followup_turn=True,
    )
    assert "LONGITUDINAL COMPARISONS" in sys_compare
    assert "FORMAT FOR FOLLOW-UP TURNS" in sys_compare
    assert "### 🟢 The Short Version" not in sys_compare

    # 2. Trend follow-up
    sys_trend, _ = build_prompt(
        user_query="show trend for my blood sugar over time",
        is_followup_turn=True,
    )
    assert "LONGITUDINAL COMPARISONS" in sys_trend
    assert "### 🟢 The Short Version" not in sys_trend

    # 3. Non-comparison follow-up
    sys_no_comp, _ = build_prompt(
        user_query="what should I do to improve",
        is_followup_turn=True,
    )
    assert "LONGITUDINAL COMPARISONS" not in sys_no_comp
    assert "FORMAT FOR FOLLOW-UP TURNS" in sys_no_comp

    # 4. Initial turn
    sys_init, _ = build_prompt(
        user_query="Explain my new lab report",
        is_followup_turn=False,
    )
    assert "### 🟢 The Short Version" in sys_init
    assert "LONGITUDINAL COMPARISONS" in sys_init


@pytest.mark.asyncio
async def test_route_followup_emergency_disclaimer_preservation():
    """
    Route-level test of follow-up turn on a document session:
    - Control: Ordinary follow-up ('what about my platelets') has ZERO Disclaimer:.
    - Emergency: Medical emergency query ('severe chest pain... is my hemoglobin okay')
      sets emergency_banner, reaches LLM, and preserves EXACTLY ONE Disclaimer:.
    """
    import pymupdf as fitz
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import MagicMock, AsyncMock, patch
    from sqlalchemy.future import select
    from app.main import app
    from app.db.database import AsyncSessionLocal
    from app.db.models import User, Chat
    from app.core.auth import get_password_hash
    from tests.conftest import TEST_PASSWORD
    from tests.test_query_stream import FakeEmbedder
    import asyncio
    import uuid

    transport = ASGITransport(app=app)

    def fake_stream(*args, **kwargs):
        chunk = MagicMock()
        chunk.text = "Your hemoglobin is 14.2 g/dL, which is within normal limits."
        return [chunk]

    mock_client = MagicMock()
    mock_client.models.generate_content_stream.side_effect = fake_stream
    mock_client.models.generate_content.side_effect = lambda *args, **kwargs: MagicMock(text="DOCUMENT_QA")

    with (
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
        patch("app.services.chat_indexer.get_embedder", return_value=FakeEmbedder()),
        patch("app.rag.embedder.get_embedder", return_value=FakeEmbedder()),
        patch("google.genai.Client", return_value=mock_client),
        patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email = f"emerg_followup_{uuid.uuid4().hex[:8]}@test.com"
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

            login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
            assert login_res.status_code == 200
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Upload a PDF
            doc = fitz.open()
            page = doc.new_page()
            page.insert_text(
                (50, 72),
                "Complete Blood Count Report. Patient: Jane Doe. Hemoglobin: 14.2 g/dL (ref 12.0 - 15.5) Normal. Glucose: 95 mg/dL (ref 70 - 99) Normal. Platelet count 250000 /uL. All other hematology parameters within normal limits."
            )
            pdf_bytes = doc.tobytes()

            up_res = await ac.post("/upload", files={"file": ("report.pdf", pdf_bytes, "application/pdf")}, headers=headers)
            assert up_res.status_code == 202
            job_id = up_res.json()["job_id"]
            doc_id = None
            for _ in range(50):
                st_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
                if st_res.status_code == 200 and st_res.json()["status"] == "completed":
                    doc_id = st_res.json()["document_id"]
                    break
                await asyncio.sleep(0.05)
            assert doc_id is not None, f"Document upload must complete: {st_res.json()}"

            # Turn 1: Initial document overview query
            res1 = await ac.post("/query", json={"session_id": str(doc_id), "query": "Explain my lab report"}, headers=headers)
            assert res1.status_code == 200

            # Turn 2: Control - ordinary follow-up query
            res_ctrl = await ac.post("/query", json={"session_id": str(doc_id), "query": "What about my platelets?"}, headers=headers)
            assert res_ctrl.status_code == 200
            assert "Disclaimer:" not in res_ctrl.text, "Ordinary follow-up must NOT have any disclaimer"

            # Turn 3: Emergency follow-up query that sets emergency_banner but continues to LLM
            res_emerg = await ac.post(
                "/query",
                json={
                    "session_id": str(doc_id),
                    "query": "I am having severe chest pain and pressure. Is my hemoglobin okay?",
                },
                headers=headers,
            )
            assert res_emerg.status_code == 200
            assert "EMERGENCY WARNING" in res_emerg.text
            # Assert exactly one Disclaimer: in final text
            assert res_emerg.text.count("Disclaimer:") == 1, (
                f"Emergency follow-up must preserve exactly one disclaimer, found {res_emerg.text.count('Disclaimer:')}"
            )

            # Also check persisted AI chat message in DB
            async with AsyncSessionLocal() as session:
                chats = (
                    await session.execute(
                        select(Chat)
                        .filter(Chat.user_id == user_id, Chat.role == "ai")
                        .order_by(Chat.created_at.desc())
                    )
                ).scalars().all()
                latest_ai_chat = chats[0]
                assert latest_ai_chat.message.count("Disclaimer:") == 1

            from app.api.v1.endpoints.upload import _background_warm_tasks
            if _background_warm_tasks:
                await asyncio.gather(*list(_background_warm_tasks), return_exceptions=True)
            from app.api.v1.endpoints.query import _background_tasks
            if _background_tasks:
                await asyncio.gather(*list(_background_tasks), return_exceptions=True)


def test_clean_disclaimers_mid_text_anchoring():
    """
    Test Item 2: _clean_disclaimers mid-text anchoring
    - 'The footer says Disclaimer: results are indicative. Next sentence stays.' on non-critical follow-up
      keeps surrounding text.
    - A line starting with '**Disclaimer:**' is still stripped on non-critical follow-up.
    - First-turn dedupe behavior is unchanged.
    """
    from app.api.v1.endpoints.query import _clean_disclaimers
    from app.rag.safety import DISCLAIMER_TEXT

    # 1. Mid-text Disclaimer: mention must be preserved on non-critical follow-up
    mid_text = "The footer says Disclaimer: results are indicative. Next sentence stays."
    res_mid = _clean_disclaimers(mid_text, is_followup_turn=True, has_critical_alert=False)
    assert res_mid == mid_text, f"Mid-text disclaimer mention must keep surrounding text, got: {repr(res_mid)}"

    # 2. Line starting with **Disclaimer:** (or with divider) is still stripped on non-critical follow-up
    line_start_text = "Here are your results.\n\n**Disclaimer:** This explanation is educational only."
    res_line_start = _clean_disclaimers(line_start_text, is_followup_turn=True, has_critical_alert=False)
    assert res_line_start == "Here are your results."

    divider_text = "Here are your results.\n\n***\n\n**Disclaimer:** This explanation is educational only."
    res_divider = _clean_disclaimers(divider_text, is_followup_turn=True, has_critical_alert=False)
    assert res_divider == "Here are your results."

    # 3. First-turn dedupe behavior unchanged
    single_turn1 = "Here are your results." + DISCLAIMER_TEXT
    res_single = _clean_disclaimers(single_turn1, is_followup_turn=False)
    assert res_single == single_turn1

    double_turn1 = "Here are your results." + DISCLAIMER_TEXT + DISCLAIMER_TEXT
    res_double = _clean_disclaimers(double_turn1, is_followup_turn=False)
    assert res_double.count("Disclaimer:") == 1
    assert "Here are your results." in res_double



