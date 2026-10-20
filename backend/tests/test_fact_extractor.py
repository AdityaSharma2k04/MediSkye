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


@pytest.mark.asyncio
async def test_extract_facts_semantic_deduplication_batch_embedding():
    sample_response_json = """{
      "facts": [
        {"type": "condition", "text": "High blood pressure", "confidence": 0.95},
        {"type": "condition", "text": "Asthma", "confidence": 0.90}
      ],
      "retractions": []
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = sample_response_json
    mock_client.models.generate_content.return_value = mock_response

    existing_facts = [
        {"id": "exist-1", "type": "condition", "text": "Hypertension"},
    ]

    mock_embedder = MagicMock()
    # "High blood pressure" and "Hypertension" will have high cosine similarity (identical unit vectors)
    # "Asthma" has orthogonal vector
    def mock_embed_documents(texts):
        res = []
        for t in texts:
            if "pressure" in t.lower() or "hypertension" in t.lower():
                res.append([1.0, 0.0, 0.0])
            else:
                res.append([0.0, 1.0, 0.0])
        return res

    mock_embedder.embed_documents.side_effect = mock_embed_documents

    with patch("google.genai.Client", return_value=mock_client), \
         patch("app.rag.embedder.get_embedder", return_value=mock_embedder):
        messages = ["Patient mentions high blood pressure and asthma."]
        res = await extract_facts(messages=messages, existing_facts=existing_facts, user_id=uuid.uuid4())

        # "High blood pressure" matches "Hypertension" semantically (> 0.85), so only "Asthma" remains
        assert len(res["facts"]) == 1
        assert res["facts"][0]["text"] == "Asthma"
        # Ensure embed_documents was called once with the unique strings in batch
        assert mock_embedder.embed_documents.call_count == 1
        called_texts = mock_embedder.embed_documents.call_args[0][0]
        assert "High blood pressure" in called_texts
        assert "Hypertension" in called_texts


@pytest.mark.asyncio
async def test_extract_facts_embedding_failure_falls_back_cleanly():
    sample_response_json = """{
      "facts": [
        {"type": "condition", "text": "High blood pressure", "confidence": 0.95}
      ],
      "retractions": []
    }"""

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = sample_response_json
    mock_client.models.generate_content.return_value = mock_response

    mock_embedder = MagicMock()
    mock_embedder.embed_documents.side_effect = RuntimeError("Embedding service 429 rate limit")

    existing_facts = [
        {"id": "exist-1", "type": "condition", "text": "Hypertension"},
    ]

    with patch("google.genai.Client", return_value=mock_client), \
         patch("app.rag.embedder.get_embedder", return_value=mock_embedder):
        messages = ["Patient mentions high blood pressure."]
        # Should not raise exception even when embedder fails
        res = await extract_facts(messages=messages, existing_facts=existing_facts, user_id=uuid.uuid4())
        assert len(res["facts"]) == 1
        assert res["facts"][0]["text"] == "High blood pressure"


