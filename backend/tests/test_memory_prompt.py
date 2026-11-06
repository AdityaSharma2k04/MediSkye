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

    system_instruction, user_content = build_prompt(
        user_query="How do my results look?",
        patient_facts=formatted_facts,
    )

    assert "<remembered_facts>" in user_content
    assert "Type 2 Diabetes" in user_content
    assert "Metformin 500mg twice daily" in user_content
    assert "</remembered_facts>" in user_content


def test_past_chunks_appear_only_when_provided():
    past_chunks = [
        {"chunk_text": "User discussed fasting glucose levels with doctor."}
    ]
    formatted_past = format_past_chats_for_prompt(past_chunks)

    # In DOCUMENT_QA (build_prompt)
    _sys, user_content_with_past = build_prompt(
        user_query="Follow up on glucose",
        past_chats=formatted_past,
    )
    assert "<relevant_past_conversations>" in user_content_with_past
    assert "User discussed fasting glucose levels" in user_content_with_past

    # In GENERAL_HEALTH without past_chats
    _sys2, user_content_without_past = build_general_health_prompt(
        user_query="What is normal glucose?",
        past_chats=None,
    )
    assert "<relevant_past_conversations>" not in user_content_without_past


def test_empty_facts_dont_add_empty_tags():
    _sys, user_content = build_prompt(
        user_query="What are my lab results?",
        patient_facts=None,
        past_chats=None,
    )
    prompt_context = user_content.split("<user_question>")[0]
    assert "<remembered_facts>" not in prompt_context
    assert "<relevant_past_conversations>" not in prompt_context

    _sys2, user_content_empty_str = build_prompt(
        user_query="What are my lab results?",
        patient_facts="   ",
        past_chats="",
    )
    prompt_empty_context = user_content_empty_str.split("<user_question>")[0]
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

    _sys, user_content = build_prompt(
        user_query="Compare my blood and cholesterol reports",
        retrieved_docs=[doc1, doc2],
    )

    assert "<uploaded_documents>" in user_content
    assert 'name="CBC_Jan_2026.pdf"' in user_content
    assert 'name="Lipid_Aug_2026.pdf"' in user_content
    assert "Hemoglobin: 14.5 g/dL" in user_content
    assert "Total Cholesterol: 240 mg/dL" in user_content


def test_lifestyle_fields_appear_correctly():
    class MockProfile:
        diet_type = "vegetarian"
        activity_level = "moderate (runs 3x/week)"
        height_cm = 175.0
        occupation = "software engineer"

    facts_by_type = {}
    formatted_facts = format_facts_for_prompt(facts_by_type, profile=MockProfile())

    system_instruction, user_content = build_prompt(
        user_query="Does my diet affect my cholesterol?",
        patient_facts=formatted_facts,
        height_cm=175.0,
        diet_type="vegetarian",
        activity_level="moderate",
        occupation="software engineer",
    )

    # Check both system_instruction and user_content for patient context
    combined = system_instruction + "\n" + user_content
    assert "Diet: vegetarian" in combined
    assert "Height: 175" in combined
    assert "Occupation: software engineer" in combined


def test_prior_lab_reports_history_injection():
    """Verify that prior_documents_metrics injects <prior_lab_reports_history> with exact filename and biomarkers."""
    prior_metrics = [
        {
            "filename": "Comprehensive Laboratory Report - Aarav Verma.pdf",
            "title": "Comprehensive Laboratory Report - Aarav Verma",
            "uploaded_at": "2026-10-14",
            "metrics": [
                {"test": "Serum Ferritin", "value": "44.0", "unit": "ng/mL", "range": "30.0 - 400.0", "status": "Normal"},
                {"test": "Hemoglobin", "value": "15.4", "unit": "g/dL", "range": "13.0 - 17.0", "status": "Normal"},
                {"test": "AST", "value": "31", "unit": "U/L", "range": "10 - 40", "status": "Normal"},
                {"test": "Uric Acid", "value": "5.8", "unit": "mg/dL", "range": "3.5 - 7.2", "status": "Normal"},
            ],
        }
    ]

    _sys, user_content = build_prompt(
        user_query="What changed compared to my baseline report?",
        prior_documents_metrics=prior_metrics,
    )

    assert "<prior_lab_reports_history>" in user_content
    assert 'filename="Comprehensive Laboratory Report - Aarav Verma.pdf"' in user_content
    assert "Serum Ferritin: 44.0 ng/mL" in user_content
    assert "Hemoglobin: 15.4 g/dL" in user_content
    assert "AST: 31 U/L" in user_content
    assert "Uric Acid: 5.8 mg/dL" in user_content
    assert "</prior_lab_reports_history>" in user_content


def test_format_past_chats_provenance_attribution():
    """Verify semantic past chunks are formatted with exact document filename or session title."""
    chunks = [
        {
            "text": "Discussed ferritin dropping and fatigue symptoms.",
            "doc_name": "Comprehensive Laboratory Report - Aarav Verma.pdf",
            "doc_date": "2026-10-14",
        },
        {
            "text": "User inquired about creatine monohydrate dosage and sprint recovery.",
            "session_title": "Creatine and Sprint Training",
            "created_at": "2026-11-01",
        },
    ]

    formatted = format_past_chats_for_prompt(chunks)
    assert '(From prior report: "Comprehensive Laboratory Report - Aarav Verma.pdf" / 2026-10-14)' in formatted
    assert "Discussed ferritin dropping and fatigue symptoms." in formatted
    assert '(From prior conversation: "Creatine and Sprint Training" on 2026-11-01)' in formatted
    assert "User inquired about creatine monohydrate dosage" in formatted


def test_format_facts_source_report_attribution():
    """Verify facts are formatted with [Source Report: {filename}] provenance."""
    class MockFactWithDoc:
        fact_text = "Serum Ferritin: 44.0 ng/mL"
        last_seen_at = None
        first_seen_at = None
        source_doc_name = "Comprehensive Laboratory Report - Aarav Verma.pdf"

    facts_by_type = {
        "measurement": [MockFactWithDoc()],
    }

    formatted = format_facts_for_prompt(facts_by_type)
    assert "[Source Report: Comprehensive Laboratory Report - Aarav Verma.pdf]" in formatted
    assert "Serum Ferritin: 44.0 ng/mL" in formatted


def test_prompt_builder_forbids_previously_discussed_and_enforces_exact_citations():
    """Verify system instructions explicitly forbid '[previously discussed]' and enforce exact citations and directionality."""
    sys_doc_qa, _ = build_prompt(user_query="How do my reports compare?")
    assert 'NEVER write "[previously discussed]"' in sys_doc_qa
    assert "CLINICAL DIRECTIONALITY & ZERO CONTRADICTIONS" in sys_doc_qa
    assert "LONGITUDINAL COMPARISONS & PRIOR REPORT HISTORY" in sys_doc_qa
    assert "Markdown table" in sys_doc_qa
    assert "PROACTIVE BORDERLINE & SUBCLINICAL TREND DETECTION" in sys_doc_qa
    assert "DEEP MULTI-FACTOR PROFILE SYNTHESIS" in sys_doc_qa
    assert "Strict Lactose Intolerance" in sys_doc_qa
    assert "NSAID-induced bronchospasm" in sys_doc_qa

    sys_general, _ = build_general_health_prompt(user_query="Can ferritin drop without anemia?")
    assert 'NEVER write "[previously discussed]"' in sys_general
    assert "Never group Low" in sys_general
