"""
Unit & Integration Tests for Follow-Up Quality Rules, Prompt Enhancements,
and Medication Change Query Disclaimer Preservation.
"""

import pytest
import re
from app.rag.prompt_builder import (
    FOLLOWUP_TURN_RULES,
    SHARED_CORE_RULES,
    REPORT_WALKTHROUGH_RULES,
    COMPARISON_RULES,
    _COMPARISON_REQUEST_RE,
    _select_report_instructions,
    _cap_at_sentence_boundary,
    condense_chat_history,
    build_prompt,
    build_general_health_prompt,
    DOCTOR_INSTRUCTIONS,
)
from app.api.v1.endpoints.query import (
    is_medication_change_query,
    _clean_disclaimers,
    _MEDICATION_CHANGE_QUERY_RE,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. FOLLOWUP_TURN_RULES Clauses Verification
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_turn_rules_clauses_present():
    """Verify all 15 key clauses from the upgraded FOLLOWUP_TURN_RULES specification."""
    rules = FOLLOWUP_TURN_RULES

    # Direct answer & format
    assert "Answer the user's actual question in the first or second sentence." in rules
    assert "No headings (###), no Short Version, no 'What This Report Does Not Cover', no closing disclaimer" in rules
    assert "Keep it conversational and compact: usually under 250 words" in rules

    # Warmth & natural openings
    assert "WARMTH & NATURAL OPENINGS: Open with one short, specific sentence" in rules
    assert "Never open by praising the question or the user" in rules
    assert "Do not use the words 'guidepost', 'guideposts', or 'step-by-step'" in rules
    assert "do not repeat the same reassurance phrase across turns" in rules

    # Honest reassurance & clinical priority
    assert "HONEST REASSURANCE & CLINICAL PRIORITY: Never tell the user 'not to worry', 'no need to panic', or that they are in 'fantastic shape'" in rules
    assert "rank all out-of-range findings by clinical importance first" in rules

    # Emotional questions
    assert "EMOTIONAL QUESTIONS: If the user asks an emotional question" in rules

    # Actionable guidance
    assert "ACTIONABLE GUIDANCE ('what should I do', 'how do I improve')" in rules
    assert "give 3 to 5 short, practical actions" in rules

    # Tentative causal language
    assert "TENTATIVE CAUSAL LANGUAGE: Keep all causal explanations tentative" in rules
    assert "Never write over-certain phrases such as 'highly likely', 'absolutely', 'exactly why'" in rules
    assert "'rather than a sign of organ damage'" in rules

    # Lab interference neutrality
    assert "LAB INTERFERENCE NEUTRALITY: When noting that a supplement or medication (for example biotin) can affect a laboratory test, do not state which direction it moves a result" in rules

    # Medicines & supplements
    assert "MEDICINES & SUPPLEMENTS: Never name a medicine or supplement the user is not already taking as an option" in rules
    assert "If the user asks about stopping, skipping, or changing a prescribed medicine, tell them to keep taking it as prescribed" in rules

    # Kidney & electrolyte caution
    assert "KIDNEY & ELECTROLYTE CAUTION: When eGFR is below 60 or electrolytes (such as potassium, sodium, calcium, or phosphorus) are out of range" in rules
    assert "do not list specific foods, meal swaps, protein amounts, or fluid targets" in rules

    # Unsolicited follow-up tests suppression
    assert "SUPPRESS UNSOLICITED FOLLOW-UP TESTS & RETEST TIMING: Follow-up tests and retest timing (including those in <analysis_hints>) belong to the initial walkthrough" in rules

    # Closing
    assert "CLOSING: End with one short, warm, forward-looking sentence worded differently each time. Do not end with a question" in rules


# ─────────────────────────────────────────────────────────────────────────────
# 2. Six Surgical prompt_builder.py Edits
# ─────────────────────────────────────────────────────────────────────────────

def test_six_surgical_prompt_builder_edits():
    """Verify all 6 surgical prompt edits across SHARED_CORE_RULES, REPORT_WALKTHROUGH_RULES, COMPARISON_RULES, and instructions."""
    # Edit a: Planted stock words removed from SHARED_CORE_RULES
    assert "(reminding the user, in fresh wording each time, that out-of-range values are something they and their doctor can work through together)" in SHARED_CORE_RULES
    assert "guideposts they and their doctor can address step by step" not in SHARED_CORE_RULES

    # Edit b: Sun exposure / outdoor time assumption forbidden
    assert "Never assume an unstated diet, supplement, workout, job, sun exposure or outdoor time, or condition." in SHARED_CORE_RULES

    # Edit c: Do not assume referring doctor prescribes medicines
    assert "Do not assume that the doctor named as referrer on a report prescribes the user's medicines." in SHARED_CORE_RULES

    # Edit d: Strengthened verified_absent_adjacent_tests in REPORT_WALKTHROUGH_RULES Item 6
    assert "and when that list is empty or says none, write no bullet about absent tests and name no test (for example, never say that a CBC, iron studies, or ferritin is not included). Never create such a list yourself." in REPORT_WALKTHROUGH_RULES

    # Edit e: Enforce ↘ Normal (Notable Drop) badge in COMPARISON_RULES
    assert "give it the Status `↘ Normal (Notable Drop)` (not `✓ Normal`) and mention the drop in that marker's interpretation." in COMPARISON_RULES

    # Edit f: Rule 5 updated in build_prompt and build_general_health_prompt
    _, user_content_doc = build_prompt(user_query="What about my iron?", is_followup_turn=True)
    expected_rule_5 = (
        "5. DO NOT render a comparison or longitudinal table unless the user explicitly asked to compare reports or see trends. "
        "Follow the FOLLOW-UP TURN RULES in your instructions: open with a specific sentence (never praise the question), "
        "stay under 250 words, keep causes tentative, and leave out follow-up tests and retest timing unless they answer this question.\n"
    )
    assert expected_rule_5 in user_content_doc

    _, user_content_gen = build_general_health_prompt(user_query="What about my diet?", is_followup_turn=True)
    assert expected_rule_5 in user_content_gen


# ─────────────────────────────────────────────────────────────────────────────
# 3. Narrowed _COMPARISON_REQUEST_RE & Instructions Selector
# ─────────────────────────────────────────────────────────────────────────────

def test_comparison_request_re_selector_cases():
    """Verify precision of _COMPARISON_REQUEST_RE on positive and negative cases."""
    # Negatives: simple past or factual questions about past reports
    negatives = [
        "What did my last report say about ferritin?",
        "What did my previous report show for TSH?",
        "Did my last test have vitamin D?",
        "What was my creatinine on the earlier test?",
        "Tell me about my previous results.",
    ]
    for q in negatives:
        assert not _COMPARISON_REQUEST_RE.search(q), f"Expected False for negative query: '{q}'"
        # Selector should NOT include COMPARISON_RULES
        prompt_str = _select_report_instructions(is_followup_turn=True, user_query=q)
        assert "LONGITUDINAL COMPARISONS" not in prompt_str

    # Positives: explicit comparison or trend queries
    positives = [
        "Compare this with my last report",
        "How did my ALT change from my last report?",
        "Any trends since my previous report?",
        "Show me a comparison table",
        "Compare baseline versus follow-up",
        "What is the difference between my last and current report?",
        "How has my uric acid changed since baseline?",
        "Show me the trend over time",
        "Put them side by side",
        "Can you compare my earlier results with current ones?",
    ]
    for q in positives:
        assert _COMPARISON_REQUEST_RE.search(q), f"Expected True for comparison query: '{q}'"
        # Selector MUST include COMPARISON_RULES
        prompt_str = _select_report_instructions(is_followup_turn=True, user_query=q)
        assert "LONGITUDINAL COMPARISONS" in prompt_str


def test_select_report_instructions_turn_1():
    """Turn 1 always includes full walkthrough and comparison rules."""
    prompt_str = _select_report_instructions(is_followup_turn=False, user_query="Explain my labs")
    assert prompt_str == DOCTOR_INSTRUCTIONS
    assert "### 🟢 The Short Version" in prompt_str
    assert "LONGITUDINAL COMPARISONS" in prompt_str


# ─────────────────────────────────────────────────────────────────────────────
# 4. 500-Character Assistant History Condenser Cap
# ─────────────────────────────────────────────────────────────────────────────

def test_condenser_500_char_cap():
    """Test that assistant history is capped at 500 chars (not 350), preserving trailing cautions."""
    # Text with 420 chars ending with period
    sentence_1 = "Your potassium level is currently 5.4 mmol/L, which is slightly above the standard laboratory reference range. "
    sentence_2 = "Because elevated potassium can affect heart rhythm, it is especially important to review high-potassium foods and dietary patterns with your doctor. "
    sentence_3 = "Avoid salt substitutes that contain potassium until your clinician evaluates these results and determines whether follow-up testing is appropriate."
    long_msg = sentence_1 + sentence_2 + sentence_3
    msg_len = len(long_msg)
    assert 360 < msg_len <= 500

    # Under 350-char cap, sentence 3 would be lost. Under 500-char cap, it is preserved!
    capped = _cap_at_sentence_boundary(long_msg, max_chars=500)
    assert sentence_3 in capped
    assert capped == long_msg

    # Test via condense_chat_history
    chats = [
        {"role": "user", "message": "Why is my potassium high?"},
        {"role": "assistant", "message": long_msg},
    ]
    condensed = condense_chat_history(chats)
    assert sentence_3 in condensed


# ─────────────────────────────────────────────────────────────────────────────
# 5. Medication Change Query Detection & Disclaimer Preservation
# ─────────────────────────────────────────────────────────────────────────────

def test_is_medication_change_query_positives():
    positives = [
        "should I stop taking my Telmisartan immediately on my own?",
        "can i skip my metformin tonight",
        "is it okay to double my dose",
        "is it ok to double my dose",
        "do i need to quit taking my atorvastatin",
        "can i discontinue my amlodipine",
        "should i stop using my inhaler",
        "can I stop my blood pressure medicine",
        "do I need to stop taking my pills",
    ]
    for q in positives:
        assert is_medication_change_query(q) is True, f"Expected medication change detection for: '{q}'"


def test_is_medication_change_query_negatives():
    negatives = [
        "why did my ferritin drop",
        "what should i do to fix my health",
        "should i take iron with vitamin C",
        "how do i stop feeling tired",
        "can i eat grapefruit with medication",
        "is it safe to exercise today",
        "",
        None,
    ]
    for q in negatives:
        assert is_medication_change_query(q) is False, f"Expected negative for: '{q}'"


def test_route_level_disclaimer_preservation_for_medication_change():
    """
    Test that on follow-up turns:
    - Normal queries have disclaimers stripped by _clean_disclaimers.
    - Medication change queries preserve the single clinical disclaimer!
    """
    sample_text = (
        "You should continue taking your prescribed medication until consulting your clinician.\n\n"
        "**Disclaimer:** This explanation is for educational purposes only and is not a substitute for professional medical advice."
    )

    # Normal follow-up (has_critical_alert=False): disclaimer is stripped
    normal_followup = _clean_disclaimers(sample_text, is_followup_turn=True, has_critical_alert=False)
    assert "**Disclaimer:**" not in normal_followup

    # Medication change follow-up (has_critical_alert=True): disclaimer is PRESERVED
    med_query = "should I stop taking my Telmisartan immediately on my own?"
    has_critical = is_medication_change_query(med_query)
    assert has_critical is True

    med_followup = _clean_disclaimers(sample_text, is_followup_turn=True, has_critical_alert=has_critical)
    assert "**Disclaimer:**" in med_followup
    assert "This explanation is for educational purposes only" in med_followup
