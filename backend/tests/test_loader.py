import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document

from app.rag.loader import extract_text_from_file, PDFExtractionError, MIN_EXTRACTED_CHARS


@pytest.mark.anyio
async def test_ocr_not_called_when_native_extraction_sufficient():
    sufficient_text = "Patient Blood Test Results: Hemoglobin 14.2 g/dL, WBC 6500, Platelets 250,000. All normal reference ranges."
    assert len(sufficient_text) >= MIN_EXTRACTED_CHARS

    native_docs = [Document(page_content=sufficient_text, metadata={"page": 1, "source": "pymupdf"})]

    with patch("app.rag.loader._detect_table_pages", return_value=[]), \
         patch("app.rag.loader._extract_with_pypdf2", return_value=[]), \
         patch("app.rag.loader._extract_with_pymupdf", return_value=native_docs), \
         patch("app.rag.loader._extract_with_ocr") as mock_ocr:

        docs = await extract_text_from_file("dummy.pdf", "dummy.pdf")

        assert len(docs) == 1
        assert docs[0].page_content == sufficient_text
        mock_ocr.assert_not_called()


@pytest.mark.anyio
async def test_ocr_called_as_fallback_when_native_extraction_insufficient():
    insufficient_text = "Scanned Title"
    assert len(insufficient_text) < MIN_EXTRACTED_CHARS

    native_docs = [Document(page_content=insufficient_text, metadata={"page": 1, "source": "pypdf2"})]
    ocr_text = "Detailed scanned laboratory report with full metabolic panel, electrolytes, glucose 95 mg/dL, creatinine 0.9 mg/dL."
    assert len(ocr_text) >= MIN_EXTRACTED_CHARS
    ocr_docs = [Document(page_content=ocr_text, metadata={"page": 1, "source": "ocr"})]

    with patch("app.rag.loader._detect_table_pages", return_value=[]), \
         patch("app.rag.loader._extract_with_pypdf2", return_value=native_docs), \
         patch("app.rag.loader._extract_with_pymupdf", return_value=[]), \
         patch("app.rag.loader._extract_with_ocr", return_value=ocr_docs) as mock_ocr:

        docs = await extract_text_from_file("scanned.pdf", "scanned.pdf")

        assert len(docs) == 1
        assert docs[0].page_content == ocr_text
        mock_ocr.assert_called_once_with("scanned.pdf")


@pytest.mark.anyio
async def test_ocr_fallback_raises_pdf_extraction_error_if_still_insufficient():
    insufficient_text = "Too short"

    with patch("app.rag.loader._detect_table_pages", return_value=[]), \
         patch("app.rag.loader._extract_with_pypdf2", return_value=[]), \
         patch("app.rag.loader._extract_with_pymupdf", return_value=[]), \
         patch("app.rag.loader._extract_with_ocr", return_value=[Document(page_content=insufficient_text, metadata={"page": 1})]):

        with pytest.raises(PDFExtractionError):
            await extract_text_from_file("empty.pdf", "empty.pdf")
