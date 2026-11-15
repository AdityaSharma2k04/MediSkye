"""
Unit tests for answer_lint.py (Clinical QA Linter).
"""

import pytest
try:
    from tests.answer_lint import (
        check_banned_phrases,
        check_compliment_opener,
        check_walkthrough_artifacts,
        check_conversation_repetition,
        parse_markdown_report,
        lint_conversation,
        ConversationData,
        TurnData,
    )
except ImportError:
    from backend.tests.answer_lint import (
        check_banned_phrases,
        check_compliment_opener,
        check_walkthrough_artifacts,
        check_conversation_repetition,
        parse_markdown_report,
        lint_conversation,
        ConversationData,
        TurnData,
    )


def test_check_banned_phrases_positives():
    phrases = [
        "This is highly likely the cause.",
        "That is absolutely normal.",
        "This explains exactly why your ferritin dropped.",
        "Your diet is the primary driver here.",
        "Your workout is directly connected to this spike.",
        "This result points to an issue.",
        "It points toward thyroid imbalance.",
        "This points away from kidney damage.",
        "The test confirms that you have hypothyroidism.",
        "The lab confirms the diagnosis.",
        "There is no need to worry at all.",
        "There is no need to panic right now.",
        "Your cardiovascular health is in fantastic shape.",
        "This elevation is rather than a sign of organ damage.",
    ]
    for p in phrases:
        matches = check_banned_phrases(p)
        assert len(matches) > 0, f"Expected banned match for: '{p}'"


def test_check_banned_phrases_negatives():
    clean_phrases = [
        "This can be consistent with increased physical exertion.",
        "Elevated AST may suggest muscle turnover or liver inflammation.",
        "One factor a clinician may consider is your supplement routine.",
        "Your numbers show a notable drop since baseline.",
    ]
    for p in clean_phrases:
        matches = check_banned_phrases(p)
        assert len(matches) == 0, f"Unexpected banned match for clean phrase: '{p}', got {matches}"


def test_check_compliment_opener_positives():
    positives = [
        "It is natural to wonder why these numbers shifted.",
        "It is so natural to feel curious about this.",
        "It is completely wonderful that you are following up.",
        "It is really smart to track these markers.",
        "It is incredibly wonderful how the body works.",
        "It is understandable to feel concerned.",
        "It is common to see this pattern.",
    ]
    for p in positives:
        opener = check_compliment_opener(p)
        assert opener is not None, f"Expected compliment opener for: '{p}'"


def test_check_compliment_opener_negatives():
    clean = [
        "Your ferritin level of 24 ng/mL is below the reference range.",
        "Looking at your thyroid markers, your TSH is currently 6.84 mIU/L.",
        "Creatine supplementation can elevate serum creatinine without indicating kidney injury.",
    ]
    for p in clean:
        opener = check_compliment_opener(p)
        assert opener is None, f"Unexpected compliment opener for: '{p}'"


def test_walkthrough_artifacts_in_followup():
    # 1. ### Headings in doc chat follow-up
    arts = check_walkthrough_artifacts(
        ai_response="Here is an update:\n### Liver Function\nYour ALT is normal.",
        user_prompt="What about my ALT?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert any("Forbidden ### headings" in a for a in arts)

    # 2. Table in follow-up when not requested
    table_text = "| Marker | Value |\n|---|---|\n| Ferritin | 24 |"
    arts_table = check_walkthrough_artifacts(
        ai_response=table_text,
        user_prompt="Why is my ferritin low?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert any("Unrequested Markdown table" in a for a in arts_table)

    # 3. Table allowed when requested
    arts_table_req = check_walkthrough_artifacts(
        ai_response=table_text,
        user_prompt="Can you compare this with my last report in a table?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert not any("Unrequested Markdown table" in a for a in arts_table_req)

    # 4. Disclaimer in normal follow-up
    arts_disc = check_walkthrough_artifacts(
        ai_response="Your iron is low.\n\n**Disclaimer:** For educational purposes only.",
        user_prompt="Why is my iron low?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert any("Forbidden closing Disclaimer" in a for a in arts_disc)

    # 5. Disclaimer allowed on medication change follow-up
    arts_disc_med = check_walkthrough_artifacts(
        ai_response="Keep taking your medication as prescribed.\n\n**Disclaimer:** For educational purposes only.",
        user_prompt="Should I stop taking my Telmisartan immediately on my own?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert not any("Forbidden closing Disclaimer" in a for a in arts_disc_med)

    # 6. The Short Version in follow-up
    arts_sv = check_walkthrough_artifacts(
        ai_response="### 🟡 The Short Version\nEverything is stable.",
        user_prompt="Is everything okay?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert any("The Short Version" in a for a in arts_sv)

    # 7. Does Not Cover in follow-up
    arts_dnc = check_walkthrough_artifacts(
        ai_response="What This Report Does Not Cover: imaging and blood pressure.",
        user_prompt="What did the report say?",
        is_doc_chat=True,
        is_followup=True,
    )
    assert any("Does Not Cover" in a for a in arts_dnc)


def test_walkthrough_artifacts_ignored_on_turn_1_or_general_health():
    # Walkthrough turn (is_followup=False) allows headings and tables
    arts_turn1 = check_walkthrough_artifacts(
        ai_response="### 🟢 The Short Version\n| Marker | Value |\n|---|---|",
        user_prompt="Walk me through my report",
        is_doc_chat=True,
        is_followup=False,
    )
    assert len(arts_turn1) == 0

    # General health session allows headings
    arts_gen = check_walkthrough_artifacts(
        ai_response="### Recommended Panels\nHere are blood panels to consider.",
        user_prompt="What panels should I test?",
        is_doc_chat=False,
        is_followup=True,
    )
    assert len(arts_gen) == 0


def test_conversation_repetition_checks():
    # 1. guideposts repeated > 1
    t1 = TurnData(1, "Turn 1 Walkthrough", False, "Explain report", "Out-of-range markers are guideposts.")
    t2 = TurnData(2, "Turn 2 Follow-Up", True, "What next?", "Remember these are useful guideposts.")
    conv = ConversationData("Test Patient", True, [t1, t2])
    issues = check_conversation_repetition(conv)
    assert any("guidepost" in i.message for i in issues)

    # 2. step-by-step repeated > 1
    t3 = TurnData(1, "Turn 1 Walkthrough", False, "Explain report", "We will address this step-by-step.")
    t4 = TurnData(2, "Turn 2 Follow-Up", True, "What next?", "Work through it step by step.")
    conv2 = ConversationData("Test Patient 2", True, [t3, t4])
    issues2 = check_conversation_repetition(conv2)
    assert any("step-by-step" in i.message for i in issues2)

    # 3. Unsolicited retest repetition
    t5 = TurnData(1, "Turn 1 Walkthrough", False, "Explain", "Baseline walkthrough.")
    t6 = TurnData(2, "Turn 2 Follow-Up", True, "What about my diet?", "Consider repeat testing in 8–12 weeks.")
    t7 = TurnData(3, "Turn 3 Follow-Up", True, "How about exercise?", "Check again in 8 to 12 weeks.")
    conv3 = ConversationData("Test Patient 3", True, [t5, t6, t7])
    issues3 = check_conversation_repetition(conv3)
    assert any("Unsolicited retest timing" in i.message for i in issues3)

    # 4. Question endings > 50%
    t8 = TurnData(2, "Turn 2 Follow-Up", True, "Q1", "Answer one. Would you like more details?")
    t9 = TurnData(3, "Turn 3 Follow-Up", True, "Q2", "Answer two. Shall we discuss next steps?")
    conv4 = ConversationData("Test Patient 4", True, [t5, t8, t9])
    issues4 = check_conversation_repetition(conv4)
    assert any(">50% threshold" in i.message for i in issues4)

    # 5. Word count > 300 warning
    long_text = "word " * 310
    t10 = TurnData(2, "Turn 2 Follow-Up", True, "Q", long_text)
    conv5 = ConversationData("Test Patient 5", True, [t5, t10])
    issues5 = check_conversation_repetition(conv5)
    assert any("Length Warning" == i.category for i in issues5)


def test_parse_markdown_report_structure():
    mock_md = """# QA Report
## Profile 1: Aditya Sharma (self — 22 Y / Male)
#### Question 1 — `Turn 1 Walkthrough` (1000 ms)
> **User Prompt:** Hello!
**MediSkye AI Response:**
Welcome! How can I help?
---
#### Question 2 — `Turn 2 Follow-Up` (1200 ms)
> **User Prompt:** Tell me more.
**MediSkye AI Response:**
Here is more detail.
---
## Profile 2: Aarav Verma (dep_1)
#### Question 1 — `Turn 1 Walkthrough` (2000 ms)
> **User Prompt:** Explain my report.
**MediSkye AI Response:**
### 🟢 The Short Version
All normal.
---
"""
    convs = parse_markdown_report(mock_md)
    assert len(convs) == 2
    assert "Aditya" in convs[0].profile_name
    assert not convs[0].is_doc_chat
    assert len(convs[0].turns) == 2
    assert convs[0].turns[0].user_prompt == "Hello!"
    assert convs[0].turns[1].is_followup is True

    assert "Aarav" in convs[1].profile_name
    assert convs[1].is_doc_chat
    assert len(convs[1].turns) == 1
