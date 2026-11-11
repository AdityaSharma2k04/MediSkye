"""
Tests for the table/bullet-aware MedicalTextSplitter.

Regression targets:
  - Markdown table rows must never be split across chunks (a value must stay
    with its row header).
  - Bullet runs must stay together.
  - Normal prose still splits around chunk_size.
"""

from langchain_core.documents import Document

from app.rag.chunking import MedicalTextSplitter, split_medical_documents


TABLE_MD = """| Test | Value | Unit | Reference Range |
|---|---|---|---|
| Hemoglobin | 14.2 | g/dL | 12-17 |
| WBC | 6500 | /uL | 4000-11000 |
| Platelets | 250000 | /uL | 150000-450000 |
| Glucose (Fasting) | 168 | mg/dL | 70-99 |
| HbA1c | 8.4 | % | 4.0-5.6 |
| LDL Cholesterol | 160 | mg/dL | 0-100 |
| HDL Cholesterol | 38 | mg/dL | 40-60 |
| Triglycerides | 210 | mg/dL | 0-150 |
| Creatinine | 1.4 | mg/dL | 0.7-1.2 |
| ALT | 62 | U/L | 7-40 |
"""


def _all_chunks(splitter: MedicalTextSplitter, text: str):
    return splitter.split_text(text)


def test_table_block_never_split_across_chunks():
    """A table smaller than chunk_size must remain a single intact chunk."""
    splitter = MedicalTextSplitter(chunk_size=1200, chunk_overlap=200)
    text = "Introduction paragraph about the report findings.\n\n" + TABLE_MD
    chunks = _all_chunks(splitter, text)

    # Every table row must appear in a single chunk, complete with its pipes.
    assert any(chunk.count("| Hemoglobin | 14.2 |") == 1 for chunk in chunks)
    table_chunk = next(c for c in chunks if "Hemoglobin | 14.2" in c)
    assert "| HbA1c | 8.4 |" in table_chunk
    assert "| ALT | 62 |" in table_chunk


def test_large_table_stays_intact_as_own_chunk():
    """Even when the table exceeds chunk_size, it stays in one (oversized) chunk."""
    splitter = MedicalTextSplitter(chunk_size=200, chunk_overlap=20)
    chunks = _all_chunks(splitter, "Header.\n\n" + TABLE_MD)
    table_chunk = next(c for c in chunks if "Hemoglobin | 14.2" in c)
    # All ten data rows present in that single chunk
    assert table_chunk.count("|") >= 2 * 11
    assert "| ALT | 62 |" in table_chunk


def test_bullet_run_stays_together():
    splitter = MedicalTextSplitter(chunk_size=250, chunk_overlap=20)
    bullets = (
        "- Hemoglobin is mildly low, which may cause fatigue.\n"
        "- WBC count is within normal limits.\n"
        "- Platelets are normal, suggesting no clotting concern."
    )
    text = "Findings summary:\n\n" + bullets + "\n\nA closing paragraph follows here."
    chunks = _all_chunks(splitter, text)
    bullet_chunk = next(c for c in chunks if "Hemoglobin is mildly low" in c)
    assert "WBC count is within normal limits" in bullet_chunk
    assert "no clotting concern" in bullet_chunk


def test_prose_still_splits_around_chunk_size():
    splitter = MedicalTextSplitter(chunk_size=300, chunk_overlap=0)
    long_text = ("Sentence number one about the patient history. " * 20)
    chunks = _all_chunks(splitter, long_text)
    assert len(chunks) > 1
    assert all(len(c) <= 350 for c in chunks)  # single paragraphs still bounded


def test_split_medical_documents_preserves_metadata():
    doc = Document(
        page_content="Report:\n\n" + TABLE_MD,
        metadata={"source": "cbc.pdf", "page": 3},
    )
    chunks = split_medical_documents([doc], chunk_size=300, chunk_overlap=20)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.metadata.get("source") == "cbc.pdf"
        assert c.metadata.get("page") == 3
        assert c.page_content.strip()


def test_no_tables_no_bullets_behaves_like_recursive_splitter():
    splitter = MedicalTextSplitter(chunk_size=100, chunk_overlap=0)
    text = "A plain paragraph with words. " * 10
    chunks = _all_chunks(splitter, text)
    assert len(chunks) > 1


def test_multipage_markdown_table_header_propagation():
    page1 = Document(
        page_content="| Analyte | Result | Ref Range | Units |\n|---|---|---|---|\n| Glucose | 95 | 70-99 | mg/dL |",
        metadata={"page": 1},
    )
    page2 = Document(
        page_content="| Creatinine | 1.4 | 0.7-1.2 | mg/dL |\n| Urea | 24 | 15-40 | mg/dL |",
        metadata={"page": 2},
    )
    chunks = split_medical_documents([page1, page2], chunk_size=500, chunk_overlap=0)
    page2_chunks = [c for c in chunks if c.metadata.get("page") == 2]
    assert len(page2_chunks) > 0
    assert "| Analyte | Result | Ref Range | Units |" in page2_chunks[0].page_content
    assert "|---|---|---|---|" in page2_chunks[0].page_content


def test_table_header_propagation_with_escaped_pipe_and_empty_cell():
    page1 = Document(
        page_content="| Analyte | Result | Ref Range |\n|---|---|---|\n| Glucose | 95 | 70-99 |",
        metadata={"page": 1},
    )
    # Continuation row with escaped pipe \| (still 3 cols) and empty cell (still 3 cols)
    page2 = Document(
        page_content=r"| Blood Pressure \| Sitting | 120/80 | Normal |" + "\n" + "|| 1.4 | 0.7-1.2 |",
        metadata={"page": 2},
    )
    chunks = split_medical_documents([page1, page2], chunk_size=500, chunk_overlap=0)
    page2_chunks = [c for c in chunks if c.metadata.get("page") == 2]
    assert len(page2_chunks) > 0
    assert "| Analyte | Result | Ref Range |" in page2_chunks[0].page_content
    assert "|---|---|---|" in page2_chunks[0].page_content
    assert "Blood Pressure \\| Sitting" in page2_chunks[0].page_content

