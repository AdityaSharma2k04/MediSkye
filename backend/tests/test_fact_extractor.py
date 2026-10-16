import uuid
import pytest
from unittest.mock import MagicMock, patch
from app.services.fact_extractor import extract_facts


@pytest.mark.asyncio
async def test_extract_facts_empty_messages():
    res = await extract_facts(messages=[], existing_facts=[], user_id=uuid.uuid4())
    assert res == {"facts": [], "retractions": []}


@pytest.mark.asyncio
async def test_extract_facts_mock_gemini_success():
    sample_response_json = """{
      "facts": [
        {"type": "condition", "text": "Type 2 diabetes", "detail": "diagnosed in 2019", "confidence": 1.0, "excerpt": "I've had type 2 diabetes since 2019"},
        {"type": "medication", "text": "Metformin 500mg twice daily", "detail": "daily dose", "confidence": 0.95, "excerpt": "taking metformin 500mg twice daily"}
      ],
      "retractions": [
        {"existing_fact_id": "11111111-2222-3333-4444-555555555555", "reason": "User discontinued medication"}
      ]
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = f"```json\n{sample_response_json}\n```"
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        messages = [
            {"role": "user", "content": "I've had type 2 diabetes since 2019, taking metformin 500mg twice daily."},
            {"role": "assistant", "content": "Understood. That is well noted."},
        ]
        res = await extract_facts(messages=messages, existing_facts=[], user_id=uuid.uuid4())

        assert len(res["facts"]) == 2
        assert res["facts"][0]["type"] == "condition"
        assert res["facts"][0]["text"] == "Type 2 diabetes"
        assert len(res["retractions"]) == 1
        assert res["retractions"][0]["existing_fact_id"] == "11111111-2222-3333-4444-555555555555"


@pytest.mark.asyncio
async def test_extract_facts_deduplication():
    sample_response_json = """{
      "facts": [
        {"type": "condition", "text": "Type 2 diabetes", "confidence": 1.0},
        {"type": "medication", "text": "Amlodipine 5mg", "confidence": 0.9}
      ],
      "retractions": []
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = sample_response_json
    mock_client.models.generate_content.return_value = mock_response

    existing_facts = [
        {"id": "exist-1", "type": "condition", "text": "Type 2 diabetes"},
    ]

    with patch("google.genai.Client", return_value=mock_client):
        messages = ["User says they still have diabetes and started amlodipine 5mg."]
        res = await extract_facts(messages=messages, existing_facts=existing_facts, user_id=uuid.uuid4())

        # "Type 2 diabetes" was duplicated, so only "Amlodipine 5mg" remains
        assert len(res["facts"]) == 1
        assert res["facts"][0]["type"] == "medication"
        assert res["facts"][0]["text"] == "Amlodipine 5mg"


@pytest.mark.asyncio
async def test_extract_facts_malformed_json_never_crashes():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON at all!"
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        messages = ["Hello doctor."]
        res = await extract_facts(messages=messages, existing_facts=[], user_id=uuid.uuid4())
        assert res == {"facts": [], "retractions": []}


@pytest.mark.asyncio
async def test_extract_facts_skips_when_llm_unavailable():
    from app.llm.gemini_client import GeminiUnavailableError

    with patch(
        "app.llm.gemini_client.call_gemini_with_retry",
        side_effect=GeminiUnavailableError("LLM in cooldown after recent failures"),
    ):
        messages = ["User says they have hypertension and diabetes."]
        res = await extract_facts(messages=messages, existing_facts=[], user_id=uuid.uuid4())
        assert res == {"facts": [], "retractions": []}

