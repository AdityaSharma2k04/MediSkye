"""
Retriever module — manages FAISS + BM25 hybrid indexes.

During upload: builds both a FAISS vectorstore and a BM25 keyword index
over the same document chunks.

During query: loads both indexes and performs hybrid retrieval using
Reciprocal Rank Fusion (RRF) to combine semantic and keyword results.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional

import re
from langchain_community.vectorstores.faiss import FAISS
from langchain_core.documents import Document

from collections import OrderedDict
import threading
from app.rag.chunking import MedicalTextSplitter
from app.rag.embedder import get_embedder
from app.rag.hybrid_search import BM25Index, save_bm25_index, load_bm25_index, reciprocal_rank_fusion
from app.rag.index_storage import ensure_index_local, aensure_index_local
from app.core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
RETRIEVAL_K = 8
RETRIEVAL_FETCH_K = 24
MAX_RETRIEVAL_K = 12
MAX_FETCH_K = 48

_INDEX_CACHE_LOCK = threading.Lock()
_HYBRID_INDEX_CACHE: OrderedDict[str, tuple] = OrderedDict()
MAX_CACHE_ENTRIES = 10


def _normalize_index_key(key) -> str:
    try:
        p = Path(key)
        return str(p.resolve())
    except Exception:
        return str(key).strip().lower()


def cache_hybrid_index(key, vectorstore, bm25_index) -> None:
    """Store (vectorstore, bm25_index) in in-memory LRU cache (bounded to 10 entries)."""
    if not key:
        return
    norm_key = _normalize_index_key(key)
    with _INDEX_CACHE_LOCK:
        if norm_key in _HYBRID_INDEX_CACHE:
            _HYBRID_INDEX_CACHE.move_to_end(norm_key)
            _HYBRID_INDEX_CACHE[norm_key] = (vectorstore, bm25_index)
        else:
            if len(_HYBRID_INDEX_CACHE) >= MAX_CACHE_ENTRIES:
                evicted_key, _ = _HYBRID_INDEX_CACHE.popitem(last=False)
                logger.info("Evicted index from LRU cache: %s (maxsize=%d)", evicted_key, MAX_CACHE_ENTRIES)
            _HYBRID_INDEX_CACHE[norm_key] = (vectorstore, bm25_index)


def get_cached_hybrid_index(key) -> Optional[tuple]:
    """Retrieve (vectorstore, bm25_index) from in-memory LRU cache."""
    if not key:
        return None
    query_str = str(key).strip()
    norm_key = _normalize_index_key(key)
    with _INDEX_CACHE_LOCK:
        if norm_key in _HYBRID_INDEX_CACHE:
            _HYBRID_INDEX_CACHE.move_to_end(norm_key)
            return _HYBRID_INDEX_CACHE[norm_key]
        if query_str in _HYBRID_INDEX_CACHE:
            _HYBRID_INDEX_CACHE.move_to_end(query_str)
            return _HYBRID_INDEX_CACHE[query_str]
        for k in list(_HYBRID_INDEX_CACHE.keys()):
            if query_str in k:
                _HYBRID_INDEX_CACHE.move_to_end(k)
                return _HYBRID_INDEX_CACHE[k]
    return None


def evict_index_cache(key_or_doc_id) -> None:
    """Evict index artifacts from in-memory cache by path, filename, or doc_id."""
    if not key_or_doc_id:
        return
    query_str = str(key_or_doc_id).strip()
    norm_key = _normalize_index_key(key_or_doc_id)
    with _INDEX_CACHE_LOCK:
        keys_to_remove = []
        for k in list(_HYBRID_INDEX_CACHE.keys()):
            if k == norm_key or query_str in k:
                keys_to_remove.append(k)
        for k in keys_to_remove:
            _HYBRID_INDEX_CACHE.pop(k, None)
            logger.info("Evicted index from LRU cache explicitly: %s", k)


def _build_splitter() -> MedicalTextSplitter:
    """Table/bullet-aware splitter — keeps Markdown tables and bullet runs intact."""
    return MedicalTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )


def dynamic_retrieval_k(query: str) -> int:
    """
    Scale the number of retrieved chunks to query complexity:
      - k=4  for short, single-fact questions  (<= 6 words)
      - k=6  for medium questions              (7-15 words)
      - k=12 for long or multi-part questions  (>15 words, or explicit
             multi-part markers such as extra "?" or " and "/"also" joins)
    """
    q = (query or "").strip()
    words = re.findall(r"[A-Za-z0-9]+", q)
    word_count = len(words)

    # A single trailing "?" is normal; only EXTRA question marks or explicit
    # joiners ("and", "also", "vs") signal a genuinely multi-part question.
    extra_questions = max(0, q.count("?") - 1)
    multi_part_markers = (
        extra_questions
        + q.lower().count(" and ")
        + q.lower().count(" also ")
        + q.lower().count(" vs ")
    )

    if word_count <= 6:
        k = 4
    elif word_count <= 15:
        k = 6
    else:
        k = 12

    # Promote to a broader sweep when the question explicitly bundles
    # several sub-questions (and it is long enough for that to matter).
    if multi_part_markers >= 1 and word_count >= 10:
        k = 12

    return min(k, MAX_RETRIEVAL_K)


def dynamic_fetch_k(k: int) -> int:
    """MMR fetch_k scaled to the requested k (bounded, never below the default)."""
    return max(RETRIEVAL_FETCH_K, min(3 * k, MAX_FETCH_K))


def build_hybrid_index_from_embeddings(
    chunks: list[Document],
    embeddings: list[list[float]],
    index_path: str,
):
    """
    Build FAISS vectorstore from pre-computed embeddings and build BM25 index.
    Saves both to disk at index_path.
    CPU-bound operation meant to be called within asyncio.to_thread.
    """
    embedder = get_embedder()
    chunk_texts = [c.page_content for c in chunks]
    text_embeddings = list(zip(chunk_texts, embeddings))
    metadatas = [c.metadata for c in chunks]

    # Build FAISS vectorstore from precomputed embeddings without calling API
    vectorstore = FAISS.from_embeddings(text_embeddings, embedder, metadatas=metadatas)
    vectorstore.save_local(index_path)

    # Build BM25 index over the same chunks
    bm25_index = BM25Index(chunks)
    save_bm25_index(bm25_index, index_path)

    cache_hybrid_index(index_path, vectorstore, bm25_index)
    return vectorstore, bm25_index, chunks


async def acreate_hybrid_index(page_docs: list[Document], index_path: str):
    """
    Asynchronously create hybrid index without blocking the event loop:
    1. Offload text splitting to thread pool.
    2. Embed chunks asynchronously yielding back to the event loop between chunks.
    3. Offload FAISS index and BM25 building to thread pool.
    """
    splitter = _build_splitter()
    raw_chunks = await asyncio.to_thread(splitter.split_documents, page_docs)
    chunks = [c for c in raw_chunks if c.page_content and c.page_content.strip()]
    if not chunks:
        chunks = [Document(page_content="Empty document", metadata={})]

    chunk_texts = [c.page_content for c in chunks]

    # Asynchronously retrieve embeddings yielding back to event loop after each call
    embedder = get_embedder()
    if hasattr(embedder, "aembed_documents"):
        embeddings = await embedder.aembed_documents(chunk_texts)
    else:
        embeddings = await asyncio.to_thread(embedder.embed_documents, chunk_texts)

    # Build FAISS and BM25 in worker thread
    return await asyncio.to_thread(
        build_hybrid_index_from_embeddings,
        chunks,
        embeddings,
        index_path,
    )


def create_hybrid_index(page_docs: list[Document], index_path: str):
    """
    Create both a FAISS vectorstore and a BM25 index from the same chunks.
    Saves both to disk at index_path.
    
    Returns (vectorstore, bm25_index, chunks).
    """
    splitter = _build_splitter()
    raw_chunks = splitter.split_documents(page_docs)
    chunks = [c for c in raw_chunks if c.page_content and c.page_content.strip()]
    
    # Build FAISS vectorstore
    vectorstore = FAISS.from_documents(chunks, get_embedder())
    vectorstore.save_local(index_path)
    
    # Build BM25 index over the same chunks
    bm25_index = BM25Index(chunks)
    save_bm25_index(bm25_index, index_path)
    
    cache_hybrid_index(index_path, vectorstore, bm25_index)
    return vectorstore, bm25_index, chunks


def load_hybrid_index(index_path: str):
    """
    Load both FAISS and BM25 indexes from disk, ensuring local availability via GCS if needed.
    Returns (vectorstore, bm25_index). BM25 may be None if not found.
    Checks in-memory LRU cache first for 0ms retrieval.
    """
    cached = get_cached_hybrid_index(index_path)
    if cached is not None:
        return cached

    resolved_path = str(ensure_index_local(index_path))
    vectorstore = FAISS.load_local(resolved_path, get_embedder(), allow_dangerous_deserialization=True)
    bm25_index = load_bm25_index(resolved_path)

    cache_hybrid_index(index_path, vectorstore, bm25_index)
    if resolved_path != index_path:
        cache_hybrid_index(resolved_path, vectorstore, bm25_index)

    return vectorstore, bm25_index


def add_to_vectorstore(vectorstore: FAISS, page_docs: list[Document], session_id: str = None):
    splitter = _build_splitter()
    chunks = splitter.split_documents(page_docs)
    vectorstore.add_documents(chunks)
    
    if session_id:
        save_vectorstore_to_disk(vectorstore, session_id)


def save_vectorstore_to_disk(vectorstore: FAISS, session_id: str):
    try:
        session_dir = settings.VECTOR_CACHE_DIR / session_id
        vectorstore.save_local(str(session_dir))
    except Exception as err:
        logger.warning("Failed to save vectorstore for %s: %s", session_id, err)


def retrieve_relevant_docs(
    query: str,
    vectorstore,
    bm25_index: Optional[BM25Index] = None,
    k: int = RETRIEVAL_K,
) -> list[Document]:
    """
    Hybrid retrieval: runs both FAISS (semantic) and BM25 (keyword) searches,
    then fuses results using Reciprocal Rank Fusion.
    
    If no BM25 index is available, falls back to FAISS-only MMR search
    (backward compatible with existing indexes).
    """
    # FAISS semantic search (MMR for diversity; fetch_k scales with k so a
    # wider sweep keeps enough candidates when k grows for complex queries)
    faiss_results = vectorstore.max_marginal_relevance_search(
        query,
        k=k,
        fetch_k=dynamic_fetch_k(k),
    )
    
    # If BM25 index is available, do hybrid fusion
    if bm25_index is not None:
        bm25_results = bm25_index.search(query, k=k)
        
        if bm25_results:
            # Fuse using RRF
            fused = reciprocal_rank_fusion(faiss_results, bm25_results, k=k)
            return fused
    
    # Fallback: FAISS-only with keyword boosting (original behavior)
    query_keywords = [w.lower() for w in query.split() if len(w) > 2]
    
    if query_keywords:
        similarity_docs = vectorstore.similarity_search(query, k=k)
        seen_texts = {d.page_content for d in faiss_results}
        for doc in similarity_docs:
            if doc.page_content not in seen_texts:
                faiss_results.append(doc)
                seen_texts.add(doc.page_content)
                
    return faiss_results[:k]


async def retrieve_cross_document(
    user_id,
    query: str,
    db,
    k: int = RETRIEVAL_K,
    active_doc_id = None,
    dependent_id = None,
) -> list[Document]:
    """
    Search across all documents belonging to a user/dependent.
    Loads each document's hybrid index, retrieves relevant chunks,
    and merges using reciprocal rank fusion with a boost for the active document.
    """
    import re
    import uuid
    from sqlalchemy.future import select
    from app.db.models import Document as DBDocument

    d_id = uuid.UUID(str(dependent_id)) if (dependent_id and isinstance(dependent_id, str)) else dependent_id
    filters = [
        DBDocument.user_id == user_id,
        DBDocument.dependent_id == d_id if d_id else DBDocument.dependent_id.is_(None),
    ]
    result = await db.execute(select(DBDocument).filter(*filters))
    docs = result.scalars().all()
    
    if not docs:
        return []
    
    all_doc_results = []
    
    # Sort docs so active_doc_id is first if present
    if active_doc_id:
        docs = sorted(docs, key=lambda d: 0 if d.id == active_doc_id else 1)

    for db_doc in docs:
        if not db_doc.file_path:
            continue
        try:
            resolved_path = str(await aensure_index_local(db_doc.file_path))
            if not os.path.exists(resolved_path):
                continue
            vectorstore, bm25_index = load_hybrid_index(resolved_path)
            retrieved = retrieve_relevant_docs(query, vectorstore, bm25_index, k=k)
            for d in retrieved:
                doc_name = db_doc.title or db_doc.filename
                d.metadata["source_doc"] = doc_name
                d.metadata["document_id"] = str(db_doc.id)
                d.metadata["is_active_doc"] = (db_doc.id == active_doc_id)
            if retrieved:
                all_doc_results.append(retrieved)
        except Exception as e:
            logger.warning("Failed to load index for doc %s: %s", db_doc.id, e)
            continue

    if not all_doc_results:
        return []

    if len(all_doc_results) == 1:
        return all_doc_results[0][:k]

    # Reciprocal Rank Fusion across all documents
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for doc_list in all_doc_results:
        for rank, d in enumerate(doc_list):
            key = d.page_content.strip()
            boost = 1.25 if d.metadata.get("is_active_doc") else 1.0
            scores[key] = scores.get(key, 0.0) + (boost / (60.0 + rank))
            if key not in doc_map:
                doc_map[key] = d

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys[:k]]

