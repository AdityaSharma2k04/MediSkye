"""
Hybrid Search: BM25 (keyword) + FAISS (semantic) combined via Reciprocal Rank Fusion (RRF).

During upload, a BM25 index is built over the same chunks that populate FAISS.
During query, both indexes are searched independently and the results are merged
using RRF to get the best of keyword-exact and semantic-meaning retrieval.
"""

import hashlib
import hmac
import json
import re
import logging
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


# ─── Tokenizer ──────────────────────────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    """Simple medical-friendly tokenizer: lowercase, keep numbers and decimals."""
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())


# ─── BM25 Index ─────────────────────────────────────────────────────────
class BM25Index:
    """Wraps rank_bm25.BM25Okapi with chunk metadata for retrieval."""

    def __init__(self, chunks: list[Document]):
        self.chunks = chunks
        tokenized_corpus = [_tokenize(c.page_content) for c in chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, k: int = 8) -> list[tuple[Document, float]]:
        tokens = _tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in ranked[:k]:
            if score > 0:
                results.append((self.chunks[idx], score))
        return results


# ─── Reciprocal Rank Fusion ─────────────────────────────────────────────
def reciprocal_rank_fusion(
    faiss_results: list[Document],
    bm25_results: list[tuple[Document, float]],
    k: int = 8,
    rrf_k: int = 60,
) -> list[Document]:
    """
    Merge FAISS and BM25 results using RRF.
    score(d) = sum(1 / (rrf_k + rank)) across all lists that contain d.
    """
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    # Score FAISS results (ordered by similarity — rank 0 is best)
    for rank, doc in enumerate(faiss_results):
        key = hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()[:16]
        scores[key] = scores.get(key, 0) + 1.0 / (rrf_k + rank)
        doc_map[key] = doc

    # Score BM25 results (already sorted by BM25 score descending)
    for rank, (doc, _bm25_score) in enumerate(bm25_results):
        key = hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()[:16]
        scores[key] = scores.get(key, 0) + 1.0 / (rrf_k + rank)
        doc_map[key] = doc

    # Sort by combined RRF score
    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:k]]


# ─── Persistence ─────────────────────────────────────────────────────────
def save_bm25_index(bm25_index: BM25Index, index_path: str) -> None:
    """Save tokenized corpus and metadata to JSON format alongside the FAISS index."""
    p = Path(index_path)
    stem = p.name.removesuffix(".index")
    bm25_path = p.parent / f"{stem}_bm25.json"
    bm25_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "chunks": [
            {
                "page_content": getattr(c, "page_content", ""),
                "metadata": getattr(c, "metadata", {}) or {},
            }
            for c in getattr(bm25_index, "chunks", [])
        ],
    }
    with open(bm25_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def load_bm25_index(index_path: str) -> Optional[BM25Index]:
    """Load BM25 index from JSON format if it exists. Does not use pickle."""
    p = Path(index_path)
    stem = p.name.removesuffix(".index")
    bm25_path = p.parent / f"{stem}_bm25.json"
    if not bm25_path.exists() and p.is_dir():
        bm25_path = p / f"{stem}_bm25.json"

    if bm25_path.exists():
        try:
            with open(bm25_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            chunks = [
                Document(page_content=item.get("page_content", ""), metadata=item.get("metadata", {}))
                for item in data.get("chunks", [])
                if isinstance(item, dict) and item.get("page_content")
            ]
            if chunks:
                return BM25Index(chunks)
        except Exception as e:
            logger.warning("Could not load BM25 index from JSON %s: %s", bm25_path, e)
    return None


def sign_faiss_index(index_dir: Path | str) -> Optional[Path]:
    """Compute and write HMAC-SHA256 signature for FAISS index files (index.faiss, index.pkl)."""
    target = Path(index_dir)
    if not target.exists() or not target.is_dir():
        return None
    from app.core.config import settings
    key = getattr(settings, "FERNET_KEY", None)
    hmac_key = key.encode("utf-8") if isinstance(key, str) and key.strip() else b"mediskye-default-hmac-key"
    h = hmac.new(hmac_key, digestmod=hashlib.sha256)
    for fname in sorted(["index.faiss", "index.pkl"]):
        fpath = target / fname
        if fpath.exists():
            h.update(fpath.read_bytes())
    sig_path = target / "index.sig"
    sig_path.write_text(h.hexdigest(), encoding="utf-8")
    return sig_path


def verify_faiss_index(index_dir: Path | str) -> bool:
    """
    Verify HMAC-SHA256 signature of FAISS index directory before load.
    Returns True if valid.
    If index.sig does not exist, logs a warning and returns True for backward compatibility.
    If index.sig exists but does not match, returns False (tampering detected).
    """
    target = Path(index_dir)
    sig_path = target / "index.sig"
    if not sig_path.exists():
        logger.warning("FAISS index at %s missing index.sig (legacy un-signed index). Permitting backward-compatible load.", target)
        return True
    from app.core.config import settings
    key = getattr(settings, "FERNET_KEY", None)
    hmac_key = key.encode("utf-8") if isinstance(key, str) and key.strip() else b"mediskye-default-hmac-key"
    h = hmac.new(hmac_key, digestmod=hashlib.sha256)
    for fname in sorted(["index.faiss", "index.pkl"]):
        fpath = target / fname
        if fpath.exists():
            h.update(fpath.read_bytes())
    expected = sig_path.read_text(encoding="utf-8").strip()
    return hmac.compare_digest(h.hexdigest(), expected)
