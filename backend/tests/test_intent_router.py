import pytest
from unittest.mock import MagicMock, patch

from app.core.config import settings
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

    with patch("app.rag.intent_router.call_gemini_with_retry", return_value=mock_resp) as mock_gemini:
        intent = await classify_intent("who created you and what can you help me with?")
        assert intent == QueryIntent.CASUAL
        assert mock_gemini.call_args.kwargs["model"] == settings.GEMINI_MODEL


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


@pytest.mark.asyncio
async def test_classify_intent_emergency_fast_path_no_llm_call():
    emergency_phrases = [
        "I have severe chest pain",
        "I can't breathe",
        "Patient cannot breathe properly",
        "Think I might be having a heart attack",
        "Symptoms of stroke",
        "Thinking about suicide",
        "Severe bleeding from leg",
        "Found patient unconscious on floor",
    ]
    with patch("app.rag.intent_router.call_gemini_with_retry") as mock_gemini:
        for phrase in emergency_phrases:
            intent = await classify_intent(phrase)
            assert intent == QueryIntent.EMERGENCY, f"Expected EMERGENCY for {phrase}"
        mock_gemini.assert_not_called()


@pytest.mark.asyncio
async def test_classify_intent_document_attached_fast_path_no_llm_call():
    # When a document is attached and query is not emergency/casual, return DOCUMENT_QA in 0ms without LLM
    doc_queries = [
        "What are my abnormal values?",
        "Is my hemoglobin level normal?",
        "Explain the WBC count on page 2",
        "What does high glucose mean for me?",
    ]
    with patch("app.rag.intent_router.call_gemini_with_retry") as mock_gemini:
        for q in doc_queries:
            intent = await classify_intent(q, has_document=True)
            assert intent == QueryIntent.DOCUMENT_QA
            intent_with_id = await classify_intent(q, document_id="doc-12345")
            assert intent_with_id == QueryIntent.DOCUMENT_QA
        mock_gemini.assert_not_called()


@pytest.mark.asyncio
async def test_classify_intent_emergency_and_casual_precedence_with_document():
    # Emergency and Casual must take precedence even if document is attached
    with patch("app.rag.intent_router.call_gemini_with_retry") as mock_gemini:
        assert await classify_intent("I have crushing chest pain", has_document=True) == QueryIntent.EMERGENCY
        assert await classify_intent("hello mediskye", has_document=True) == QueryIntent.CASUAL
        mock_gemini.assert_not_called()
