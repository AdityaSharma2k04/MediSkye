import hashlib
import pytest
from langchain_core.documents import Document

from app.rag.hybrid_search import reciprocal_rank_fusion


def test_rrf_no_key_collision_on_identical_prefixes():
    """
    Verify that chunks with identical first 200 chars but different tails
    produce distinct SHA256 keys and are not collapsed during RRF.
    """
    prefix = "MediSkye Diagnostic Laboratory Report Header Information " * 4  # > 200 chars
    assert len(prefix) > 200

    doc1 = Document(page_content=prefix + " Tail A: Hemoglobin 14.2 g/dL")
    doc2 = Document(page_content=prefix + " Tail B: Platelets 250,000 /uL")

    # If first 200 chars were used as key, doc1 and doc2 would collide into 1 result.
    # With SHA256 keys, both must be preserved in the merged RRF results.
    merged = reciprocal_rank_fusion(
        faiss_results=[doc1, doc2],
        bm25_results=[(doc1, 1.5), (doc2, 1.2)],
        k=5,
    )

    assert len(merged) == 2
    contents = [d.page_content for d in merged]
    assert doc1.page_content in contents
    assert doc2.page_content in contents


@pytest.mark.asyncio
async def test_empty_xray_response_yields_no_empty_chunks(tmp_path):
    """
    Verify that when Gemini Vision returns empty text for an X-ray,
    no empty chunks are indexed into the FAISS/BM25 hybrid store.
    """
    from unittest.mock import AsyncMock, patch, MagicMock
    from app.rag.loader import process_image_path
    from app.rag.retriever import create_hybrid_index

    mock_resp = MagicMock()
    mock_resp.text = "   \n\t  "

    # Minimal 1x1 PNG bytes
    dummy_img = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
        b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    class FakeEmbedder:
        def embed_documents(self, texts):
            return [[0.1] * 768 for _ in texts]

        async def aembed_documents(self, texts):
            return [[0.1] * 768 for _ in texts]

        def embed_query(self, text):
            return [0.1] * 768

        async def aembed_query(self, text):
            return [0.1] * 768

    with (
        patch("app.rag.loader.call_gemini_with_retry", new=AsyncMock(return_value=mock_resp)),
        patch("app.rag.retriever.get_embedder", return_value=FakeEmbedder()),
    ):
        doc = await process_image_path("XRAY", dummy_img, source_meta="test_xray")
        assert doc.page_content == ""

        valid_doc = Document(page_content="Valid patient report: normal cardiac silhouette and clear lung fields.")
        index_dir = str(tmp_path / "test_idx")
        vectorstore, bm25_index, indexed_chunks = create_hybrid_index([doc, valid_doc], index_path=index_dir)

        assert len(indexed_chunks) >= 1
        for chunk in indexed_chunks:
            assert chunk.page_content.strip() != ""


def test_allowed_extensions_config_harmonization():
    """Verify settings.ALLOWED_EXTENSIONS includes all four expected extensions and pdf_service reads from it."""
    from app.core.config import settings
    from app.services.pdf_service import validate_file_upload
    from fastapi import HTTPException

    # 1. Config includes all 4 extensions
    expected = [".pdf", ".jpg", ".jpeg", ".png"]
    for ext in expected:
        assert ext in settings.ALLOWED_EXTENSIONS

    # 2. Rejection of unsupported extension
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(b"some content", filename="report.exe")
    assert exc_info.value.status_code == 400
    assert "Invalid file extension" in exc_info.value.detail

    # 3. Acceptance of supported image extensions without failing extension check
    validate_file_upload(b"fake jpeg content", filename="scan.jpg")
    validate_file_upload(b"fake png content", filename="xray.png")

