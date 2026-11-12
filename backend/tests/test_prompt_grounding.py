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

def test_prompts_are_deoverfitted_and_include_cindi_empathy_rules():
    from app.rag.prompt_builder import DOCTOR_INSTRUCTIONS, GENERAL_HEALTH_INSTRUCTIONS

    for instructions in (DOCTOR_INSTRUCTIONS, GENERAL_HEALTH_INSTRUCTIONS):
        lower_inst = instructions.lower()
        # Do NOT contain hardcoded Aarav Verma values
        assert "176 pg/ml" not in lower_inst
        assert "94 ml/min" not in lower_inst
        assert "levosalbutamol" not in lower_inst
        assert "24 oct 2026" not in lower_inst
        assert "24 apr 2027" not in lower_inst

        # DO contain all 4 Cindi empathy rules
        assert "THE EMPATHETIC TONE & REASSURANCE RULE" in instructions
        assert "THE DYNAMIC REAL-WORLD ANALOGY RULE" in instructions
        assert "THE PROACTIVE SYMPTOM CORRELATION RULE" in instructions
        assert "What This Report Does Not Cover" in instructions



def test_section_3_item_1_attribute_escaping():
    from app.core.security import escape_xml_attr
    from app.rag.prompt_builder import _format_uploaded_documents, _format_prior_lab_reports

    assert escape_xml_attr(None) == ""
    assert escape_xml_attr(0) == "0"
    assert escape_xml_attr('test"quote\'') == "test&quot;quote&#x27;"

    doc = Document(page_content="Content", metadata={"source": 'file"name.pdf', "page": 0})
    res = _format_uploaded_documents(retrieved_docs=[doc])
    assert 'name="file&quot;name.pdf"' in res
    assert 'page="0"' in res

    prior = [{"filename": 'report"1.pdf', "title": "Test", "collected_at": "2026-01-01", "metrics": []}]
    res_prior = _format_prior_lab_reports(prior)
    assert 'filename="report&quot;1.pdf"' in res_prior


def test_section_3_item_2_zero_values():
    from app.rag.prompt_builder import _format_prior_lab_reports
    prior = [{
        "filename": "lab.pdf",
        "collected_at": "2026-01-01",
        "metrics": [{"test": "TestZero", "value": 0, "unit": "mg/dL", "range": "0 - 10", "status": "Normal"}]
    }]
    formatted = _format_prior_lab_reports(prior)
    assert "TestZero: 0 mg/dL" in formatted


def test_section_3_item_3_status_policy():
    from app.rag.prompt_builder import _format_prior_lab_reports
    prior = [{
        "filename": "lab.pdf",
        "collected_at": "2026-01-01",
        "metrics": [
            {"test": "UnknownTest", "value": "15", "unit": "", "range": "", "status": None},
            {"test": "StoredCrit", "value": "15", "unit": "", "range": "", "status": "Critical"},
        ]
    }]
    formatted = _format_prior_lab_reports(prior)
    assert "[Status: Unclassified]" in formatted
    assert "[Status: Critical]" in formatted


def test_section_3_item_4_dates():
    from app.rag.prompt_builder import _format_prior_lab_reports
    prior = [{
        "filename": "lab.pdf",
        "collected_at": None,
        "uploaded_at": "2026-10-15",
        "metrics": []
    }]
    formatted = _format_prior_lab_reports(prior)
    assert 'specimen_collection_date="unknown"' in formatted
    assert 'uploaded_at="2026-10-15"' in formatted
    assert ' date=' not in formatted


def test_section_3_item_5_text_before_excerpt():
    from app.rag.prompt_builder import _format_uploaded_documents
    doc_dict = [{
        "name": "doc.pdf",
        "text": "Full full document text here",
        "excerpt": "Short excerpt here",
    }]
    formatted = _format_uploaded_documents(documents=doc_dict)
    assert "Full full document text here" in formatted
    assert "Short excerpt here" not in formatted


def test_section_3_item_6_format_facts_for_prompt():
    from app.rag.prompt_builder import format_facts_for_prompt
    import datetime as dt

    # Mixed dates: aware, naive, str, None
    now_utc = dt.datetime.now(dt.timezone.utc)
    now_naive = dt.datetime(2026, 5, 1)
    date_obj = dt.date(2026, 6, 1)

    facts = [
        {"category": "weight", "fact_value": "70 kg", "extracted_at": now_utc},
        {"category": "weight", "fact_value": "71 kg", "extracted_at": now_naive},
        {"category": "weight", "fact_value": "72 kg", "extracted_at": "2026-04-01"},
        {"category": "weight", "fact_value": "69 kg", "extracted_at": None},
        {"category": "unknown_category_xyz", "fact_key": "custom_key", "fact_value": "custom_val"},
    ]

    formatted = format_facts_for_prompt(facts)
    # Check weights sorted without error
    assert "Weight history / trend:" in formatted
    assert "Other Recorded Facts:" in formatted
    assert "custom_key: custom_val" in formatted


def test_section_3_item_7_single_escaping_boundary():
    from app.rag.prompt_builder import build_prompt

    _sys, user_content = build_prompt(
        user_query="Query",
        patient_facts="Patient notes <severe> & urgent",
        past_chats="Chat history <test> & check",
    )
    # Must appear as &lt; and &amp;, never &amp;lt; or &amp;amp;
    assert "&lt;severe&gt; &amp; urgent" in user_content
    assert "&amp;lt;" not in user_content
    assert "&amp;amp;" not in user_content
    assert "&lt;test&gt; &amp; check" in user_content


def test_section_3_item_8_profile_defaults():
    from app.rag.prompt_builder import build_prompt

    _sys, user_content = build_prompt(
        user_query="My query",
        calculated_age="Unknown",
        biological_sex="Unspecified",
        pre_existing_conditions="None reported",
        current_medications="None reported",
    )
    assert "None reported" not in user_content
    assert "no health profile saved; do not assume any diet, supplements, medications or conditions" in user_content


def test_section_3_item_9_build_general_health_prompt_documents():
    from app.rag.prompt_builder import build_general_health_prompt

    doc = Document(page_content="Uploaded report content", metadata={"source": "report.pdf", "page": 1})
    _sys, user_content = build_general_health_prompt(
        user_query="Health query",
        retrieved_docs=[doc],
    )
    assert "<uploaded_documents>" in user_content
    assert "Uploaded report content" in user_content


def test_section_3_item_10_completion_cues_and_casual():
    from app.rag.prompt_builder import build_prompt, build_general_health_prompt, build_casual_prompt

    _sys1, user_c1 = build_prompt(user_query="query")
    assert not user_c1.rstrip().endswith("Explanation:")

    _sys2, user_c2 = build_general_health_prompt(user_query="query")
    assert not user_c2.rstrip().endswith("Explanation:")

    _sys3, user_c3 = build_casual_prompt(user_query="Hello", language_preference="English")
    assert not user_c3.rstrip().endswith("Response:")
    assert "<user_question>" in user_c3
    assert "<user_query>" not in user_c3
    assert "Reply in English." in _sys3


def test_section_3_item_12_summary_prompt_truncation():
    from app.rag.prompt_builder import build_document_summary_prompt

    short_text = "Short clinical report text."
    p_short = build_document_summary_prompt(short_text)
    assert "[Report text truncated at 48000 characters]" not in p_short

    long_text = "A" * 50000
    p_long = build_document_summary_prompt(long_text)
    assert "[Report text truncated at 48000 characters]" in p_long


def test_section_6_3_forbidden_tokens():
    from app.rag.prompt_builder import (
        DOCTOR_INSTRUCTIONS,
        GENERAL_HEALTH_INSTRUCTIONS,
        UNTRUSTED_CONTENT_WARNING,
        CASUAL_INSTRUCTIONS,
        build_document_summary_prompt,
    )

    all_prompts = [
        DOCTOR_INSTRUCTIONS.lower(),
        GENERAL_HEALTH_INSTRUCTIONS.lower(),
        UNTRUSTED_CONTENT_WARNING.lower(),
        CASUAL_INSTRUCTIONS.lower(),
        build_document_summary_prompt("sample").lower(),
    ]

    forbidden_literals = [
        "aarav",
        "verma",
        "176 pg/ml",
        "94 ml/min",
        "levosalbutamol",
        "24 oct 2026",
        "24 apr 2027",
    ]

    for p in all_prompts:
        for f in forbidden_literals:
            assert f not in p, f"Forbidden literal '{f}' found in prompt text!"


def test_section_6_3_single_occurrence_of_not_found_phrase():
    from app.rag.prompt_builder import build_prompt, build_general_health_prompt

    sys1, _ = build_prompt(user_query="test")
    assert sys1.count("I cannot find this in your report") == 1

    sys2, _ = build_general_health_prompt(user_query="test")
    assert sys2.count("I cannot find this in your report") == 1


def test_tag_order_in_built_prompt():
    from app.rag.prompt_builder import build_prompt
    from langchain_core.documents import Document

    doc = Document(page_content="doc text", metadata={"source": "doc.pdf", "page": 1})
    _sys, user_content = build_prompt(
        user_query="my question",
        retrieved_docs=[doc],
        patient_facts="fact 1",
        past_chats="chat 1",
        reference_ranges={"glucose": "70-99"},
        prior_documents_metrics=[{"filename": "p.pdf", "collected_at": "2026-01-01", "metrics": []}],
        active_docs_metrics=[{"test": "Hemoglobin", "value": "14", "unit": "g/dL", "range": "13-17", "status": "Normal"}],
        raw_report_text="raw report text",
    )

    tags = [
        "<patient_context>",
        "<prior_lab_reports_history>",
        "<remembered_facts>",
        "<relevant_past_conversations>",
        "<reference_ranges>",
        "<extracted_report_biomarkers",
        "<analysis_hints>",
        "<uploaded_documents>",
        "<user_question>",
    ]

    last_pos = -1
    for tag in tags:
        pos = user_content.find(tag)
        assert pos != -1, f"Tag {tag} missing in user_content"
        assert pos > last_pos, f"Tag {tag} is out of order (found at {pos}, previous tag at {last_pos})"
        last_pos = pos
