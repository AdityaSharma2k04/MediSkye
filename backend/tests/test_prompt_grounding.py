"""
Verify the clinical prompt explicitly enforces document grounding,
an anti-hallucination fallback phrase, and a warm-but-clinical tone.
"""

from langchain_core.documents import Document

from app.rag.prompt_builder import build_prompt, build_general_health_prompt


def test_document_qa_prompt_requires_grounding_in_tags():
    system_instruction, _ = build_prompt(user_query="What is my hemoglobin?")
    assert "GROUNDING RULES" in system_instruction
    assert "<uploaded_documents>" in system_instruction
    assert "<reference_ranges>" in system_instruction
    assert "only source of truth" in system_instruction


def test_document_qa_prompt_requires_explicit_not_found_phrase():
    system_instruction, _ = build_prompt(user_query="What is my ferritin?")
    assert '"I cannot find this in your report"' in system_instruction
    assert "Never guess" in system_instruction


def test_document_qa_prompt_enforces_warm_clinical_tone():
    system_instruction, _ = build_prompt(user_query="Summarize this report")
    assert "warm, empathetic, but clinical tone" in system_instruction


def test_general_health_prompt_grounds_when_tags_present():
    system_instruction, _ = build_general_health_prompt(user_query="What is cholesterol?")
    assert "I cannot find this in your report" in system_instruction


def test_meta_word_prohibition_present():
    """The system prompt must keep the explicit prohibition on meta-terminology."""
    system_instruction, _ = build_prompt(user_query="hi")
    assert "NEVER mention 'RAG', 'chunks', 'sources'" in system_instruction


def test_prompt_grounding_with_real_document_structure():
    doc = Document(
        page_content="| Hemoglobin | 14.2 | g/dL |",
        metadata={"source": "cbc.pdf", "page": 1},
    )
    _system, user_content = build_prompt(
        user_query="Is my hemoglobin normal?",
        retrieved_docs=[doc],
    )
    assert "<uploaded_documents>" in user_content
    assert "Hemoglobin | 14.2 | g/dL" in user_content
