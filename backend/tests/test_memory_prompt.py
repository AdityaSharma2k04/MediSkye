import pytest
from langchain_core.documents import Document
from app.rag.prompt_builder import build_prompt, build_general_health_prompt
from app.services.memory_formatter import (
    format_facts_for_prompt,
    format_past_chats_for_prompt,
    format_multi_doc_context,
)


def test_facts_appear_in_built_prompt():
    facts_by_type = {
        "condition": [{"fact_text": "Type 2 Diabetes"}],
        "medication": [{"fact_text": "Metformin 500mg twice daily"}],
    }
    formatted_facts = format_facts_for_prompt(facts_by_type)

    prompt = build_prompt(
        user_query="How do my results look?",
        patient_facts=formatted_facts,
    )

    assert "<remembered_facts>" in prompt
    assert "Type 2 Diabetes" in prompt
    assert "Metformin 500mg twice daily" in prompt
    assert "</remembered_facts>" in prompt


def test_past_chunks_appear_only_when_provided():
    past_chunks = [
        {"chunk_text": "User discussed fasting glucose levels with doctor."}
    ]
    formatted_past = format_past_chats_for_prompt(past_chunks)

    # In DOCUMENT_QA (build_prompt)
    prompt_with_past = build_prompt(
        user_query="Follow up on glucose",
        past_chats=formatted_past,
    )
    assert "<relevant_past_conversations>" in prompt_with_past
    assert "User discussed fasting glucose levels" in prompt_with_past

    # In GENERAL_HEALTH without past_chats
    prompt_without_past = build_general_health_prompt(
        user_query="What is normal glucose?",
        past_chats=None,
    )
    assert "<relevant_past_conversations>" not in prompt_without_past


def test_empty_facts_dont_add_empty_tags():
    prompt = build_prompt(
        user_query="What are my lab results?",
        patient_facts=None,
        past_chats=None,
    )
    prompt_context = prompt.split("<user_question>")[0]
    assert "<remembered_facts>" not in prompt_context
    assert "<relevant_past_conversations>" not in prompt_context

    prompt_empty_str = build_prompt(
        user_query="What are my lab results?",
        patient_facts="   ",
        past_chats="",
    )
    prompt_empty_context = prompt_empty_str.split("<user_question>")[0]
    assert "<remembered_facts>" not in prompt_empty_context
    assert "<relevant_past_conversations>" not in prompt_empty_context


def test_multi_doc_citations_include_document_names():
    doc1 = Document(
        page_content="Hemoglobin: 14.5 g/dL. Platelets normal.",
        metadata={"source": "CBC_Jan_2026.pdf", "page": 1}
    )
    doc2 = Document(
        page_content="Total Cholesterol: 240 mg/dL. LDL: 155 mg/dL.",
        metadata={"source": "Lipid_Aug_2026.pdf", "page": 1}
    )

    prompt = build_prompt(
        user_query="Compare my blood and cholesterol reports",
        retrieved_docs=[doc1, doc2],
    )

    assert "<uploaded_documents>" in prompt
    assert 'name="CBC_Jan_2026.pdf"' in prompt
    assert 'name="Lipid_Aug_2026.pdf"' in prompt
    assert "Hemoglobin: 14.5 g/dL" in prompt
    assert "Total Cholesterol: 240 mg/dL" in prompt


def test_lifestyle_fields_appear_correctly():
    class MockProfile:
        diet_type = "vegetarian"
        activity_level = "moderate (runs 3x/week)"
        height_cm = 175.0
        occupation = "software engineer"

    facts_by_type = {}
    formatted_facts = format_facts_for_prompt(facts_by_type, profile=MockProfile())

    prompt = build_prompt(
        user_query="Does my diet affect my cholesterol?",
        patient_facts=formatted_facts,
        height_cm=175.0,
        diet_type="vegetarian",
        activity_level="moderate",
        occupation="software engineer",
    )

    assert "Diet: vegetarian" in prompt
    assert "Height: 175" in prompt
    assert "Occupation: software engineer" in prompt
