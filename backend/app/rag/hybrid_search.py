"""
Hybrid Search: BM25 (keyword) + FAISS (semantic) combined via Reciprocal Rank Fusion (RRF).

During upload, a BM25 index is built over the same chunks that populate FAISS.
During query, both indexes are searched independently and the results are merged
using RRF to get the best of keyword-exact and semantic-meaning retrieval.
"""

import pickle
import re
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


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
        key = doc.page_content[:200]  # Use first 200 chars as unique key
        scores[key] = scores.get(key, 0) + 1.0 / (rrf_k + rank)
        doc_map[key] = doc

    # Score BM25 results (already sorted by BM25 score descending)
    for rank, (doc, _bm25_score) in enumerate(bm25_results):
        key = doc.page_content[:200]
        scores[key] = scores.get(key, 0) + 1.0 / (rrf_k + rank)
        doc_map[key] = doc

    # Sort by combined RRF score
    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:k]]


# ─── Persistence ─────────────────────────────────────────────────────────
def save_bm25_index(bm25_index: BM25Index, index_path: str) -> None:
    """Pickle the BM25 index alongside the FAISS index."""
    bm25_path = Path(index_path).parent / (Path(index_path).stem + "_bm25.pkl")
    bm25_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bm25_path, "wb") as f:
        pickle.dump(bm25_index, f)


def load_bm25_index(index_path: str) -> Optional[BM25Index]:
    """Load a pickled BM25 index if it exists."""
    bm25_path = Path(index_path).parent / (Path(index_path).stem + "_bm25.pkl")
    if bm25_path.exists():
        try:
            with open(bm25_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Warning: Could not load BM25 index from {bm25_path}: {e}")
    return None
