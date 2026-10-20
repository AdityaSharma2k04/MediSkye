import pytest
from unittest.mock import MagicMock, patch

from app.rag.intent_router import (
    QueryIntent,
    classify_intent,
    is_casual_query_fast_path,
)
from app.rag.safety import append_disclaimer, DISCLAIMER_TEXT


def test_casual_fast_path_greetings():
    # Exact and near-exact greetings should hit the fast-path
    greetings = [
        "hi",
        "Hello",
        "HEY!",
        "hi mediskye",
        "Hi, MediSkye!",
        "hello there",
        "good morning",
        "how are you?",
        "how's it going",
        "thanks",
        "Thank you so much!",
        "ok",
        "bye",
        "goodbye",
    ]
    for g in greetings:
        assert is_casual_query_fast_path(g) is True, f"Failed on: {g}"


def test_casual_fast_path_non_greetings():
    # Medical questions or document questions should NOT hit the fast-path
    non_greetings = [
        "What is my hemoglobin level?",
        "Why is my glucose high?",
        "What causes hypertension?",
        "I have chest pain",
        "Can you explain this report?",
    ]
    for q in non_greetings:
        assert is_casual_query_fast_path(q) is False, f"Unexpected match on: {q}"


@pytest.mark.asyncio
async def test_classify_intent_casual_fast_path_no_llm_call():
    # Verify that fast path returns CASUAL immediately without calling Gemini
    with patch("app.rag.intent_router.call_gemini_with_retry") as mock_gemini:
        intent = await classify_intent("hello mediskye")
        assert intent == QueryIntent.CASUAL
        mock_gemini.assert_not_called()


@pytest.mark.asyncio
async def test_classify_intent_casual_llm_fallback():
    # Non-fast-path small talk / meta-questions classified by LLM
    mock_resp = MagicMock()
    mock_resp.text = "CASUAL"

    with patch("app.rag.intent_router.call_gemini_with_retry", return_value=mock_resp):
        intent = await classify_intent("who created you and what can you help me with?")
        assert intent == QueryIntent.CASUAL


def test_append_disclaimer_conditional():
    text = "Hello! I am MediSkye, ready to assist."

    # When intent is CASUAL, disclaimer MUST NOT be appended
    res_casual = append_disclaimer(text, intent="CASUAL")
    assert res_casual == text
    assert DISCLAIMER_TEXT.strip() not in res_casual

    res_casual_enum = append_disclaimer(text, intent=QueryIntent.CASUAL)
    assert res_casual_enum == text
    assert DISCLAIMER_TEXT.strip() not in res_casual_enum

    # When intent is DOCUMENT_QA or GENERAL_HEALTH, disclaimer MUST be appended
    res_doc = append_disclaimer(text, intent="DOCUMENT_QA")
    assert DISCLAIMER_TEXT.strip() in res_doc

    res_health = append_disclaimer(text, intent="GENERAL_HEALTH")
    assert DISCLAIMER_TEXT.strip() in res_health

    # Default without intent parameter still appends disclaimer (backwards compatibility)
    res_default = append_disclaimer(text)
    assert DISCLAIMER_TEXT.strip() in res_default
