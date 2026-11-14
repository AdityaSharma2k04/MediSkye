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

    # Positive cases (should be True)
    assert is_explicit_overview_query("walk me through my report")
    assert is_explicit_overview_query("explain my lab results")
    assert is_explicit_overview_query("summarize my report")
    assert is_explicit_overview_query("give me a full breakdown of my results")
    assert is_explicit_overview_query("give me an overview of my lab report")


def test_4_history_condensing():
    """
    Test 4: When chat history has > 4 messages (or > 2 turns), older turns are compressed
    to single-line summaries '[User asked X; Doctor explained Y with key finding Z]',
    preserving exact numbers from recent turns.
    """
    try:
        from app.rag.prompt_builder import condense_chat_history
    except ImportError:
        pytest.fail("condense_chat_history helper must exist in prompt_builder.py")

    # 6 messages (3 turns)
    chats = [
        {"role": "user", "message": "What is my cholesterol level?"},
        {"role": "ai", "message": "Your total cholesterol is 240 mg/dL, which is elevated."},
        {"role": "user", "message": "What about my HDL?"},
        {"role": "ai", "message": "Your HDL is 55 mg/dL, which is in the healthy range."},
        {"role": "user", "message": "And my LDL?"},
        {"role": "ai", "message": "Your LDL is 160 mg/dL, which is above optimal."},
    ]

    condensed = condense_chat_history(chats)
    # The oldest turn should be condensed into a concise summary bracket
    assert "[User asked" in condensed or "User asked" in condensed
    # The most recent 2 turns should preserve exact numbers
    assert "55 mg/dL" in condensed
    assert "160 mg/dL" in condensed


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
