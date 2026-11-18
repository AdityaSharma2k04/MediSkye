import json
import pytest
from pathlib import Path
from langchain_core.documents import Document
from app.rag.hybrid_search import (
    BM25Index,
    save_bm25_index,
    load_bm25_index,
    sign_faiss_index,
    verify_faiss_index,
)


def test_bm25_json_serialization_and_deserialization(tmp_path):
    """Verify BM25 persists as JSON without pickle and restores successfully."""
    chunks = [
        Document(page_content="Hemoglobin: 14.5 g/dL (Reference: 13.5 - 17.5)", metadata={"page": 1}),
        Document(page_content="Fasting Blood Glucose: 95 mg/dL", metadata={"page": 2}),
        Document(page_content="Blood Pressure: 120/80 mmHg", metadata={"page": 3}),
    ]
    bm25 = BM25Index(chunks)
    index_file = tmp_path / "test_doc.index"

    # Save
    save_bm25_index(bm25, str(index_file))

    # Verify JSON file created, NOT pickle
    json_path = tmp_path / "test_doc_bm25.json"
    pkl_path = tmp_path / "test_doc_bm25.pkl"
    assert json_path.exists(), "BM25 index should be saved as JSON"
    assert not pkl_path.exists(), "BM25 index should NOT be saved as pickle"

    # Verify JSON contents
    content = json.loads(json_path.read_text(encoding="utf-8"))
    assert content["version"] == 1
    assert len(content["chunks"]) == 3
    assert "Hemoglobin" in content["chunks"][0]["page_content"]

    # Load and search
    loaded_bm25 = load_bm25_index(str(index_file))
    assert loaded_bm25 is not None
    assert len(loaded_bm25.chunks) == 3
    results = loaded_bm25.search("hemoglobin", k=1)
    assert len(results) == 1
    assert "14.5" in results[0][0].page_content


def test_faiss_hmac_signing_and_tamper_detection(tmp_path):
    """Verify FAISS index HMAC signature detects tampering and supports legacy fallback."""
    index_dir = tmp_path / "sample.index"
    index_dir.mkdir()
    (index_dir / "index.faiss").write_bytes(b"binary faiss index content")
    (index_dir / "index.pkl").write_bytes(b"docstore pickle content")

    # 1. Unsigned legacy directory returns True for backward compatibility
    assert verify_faiss_index(index_dir) is True

    # 2. Sign directory
    sig_path = sign_faiss_index(index_dir)
    assert sig_path is not None
    assert sig_path.exists()
    assert len(sig_path.read_text().strip()) == 64  # SHA256 hex digest

    # 3. Verified directory passes
    assert verify_faiss_index(index_dir) is True

    # 4. Tampering index.faiss causes verification failure
    (index_dir / "index.faiss").write_bytes(b"TAMPERED binary faiss index content")
    assert verify_faiss_index(index_dir) is False
