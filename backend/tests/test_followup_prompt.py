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
    Test 5: Given a response that already contains 'Disclaimer:' or educational disclaimer text,
    the post-generation safety filter does not append a second disclaimer.
    Also, when is_followup_turn=True, append_disclaimer must not add a disclaimer.
    """
    text_with_prompt_disclaimer = (
        "Your hemoglobin is 14.5 g/dL, which is in the normal range.\n\n"
        "**Disclaimer:** This explanation is for educational purposes only and is not a substitute for "
        "professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider "
        "with any questions regarding a medical condition."
    )

    filtered = append_disclaimer(text_with_prompt_disclaimer)
    # Count occurrences of "Disclaimer:"
    disclaimer_count = len(re.findall(r"(?i)disclaimer:", filtered))
    assert disclaimer_count == 1, f"Expected exactly 1 disclaimer, found {disclaimer_count}: {filtered}"

    # Text containing generic educational disclaimer
    text_with_generic = "All markers look good. This information is for educational purposes only."
    filtered_generic = append_disclaimer(text_with_generic)
    assert len(re.findall(r"(?i)disclaimer:", filtered_generic)) <= 1

    # On follow-up turns, no disclaimer should be appended if is_followup_turn=True
    text_followup = "Your platelets are 250,000 /mcL, well within normal limits."
    filtered_followup = append_disclaimer(text_followup, is_followup_turn=True)
    assert "Disclaimer:" not in filtered_followup


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

