"""
Retriever module — manages FAISS + BM25 hybrid indexes.

During upload: builds both a FAISS vectorstore and a BM25 keyword index
over the same document chunks.

During query: loads both indexes and performs hybrid retrieval using
Reciprocal Rank Fusion (RRF) to combine semantic and keyword results.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.rag.embedder import get_embedder
from app.rag.hybrid_search import BM25Index, save_bm25_index, load_bm25_index, reciprocal_rank_fusion
from app.core.config import settings

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
RETRIEVAL_K = 8
RETRIEVAL_FETCH_K = 24


def _build_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )


def create_vectorstore(page_docs: list[Document], session_id: str = None):
    """Create a FAISS vectorstore from document chunks."""
    splitter = _build_splitter()
    chunks = splitter.split_documents(page_docs)
    vectorstore = FAISS.from_documents(chunks, get_embedder())
    
    if session_id:
        save_vectorstore_to_disk(vectorstore, session_id)
        
    return vectorstore


def create_hybrid_index(page_docs: list[Document], index_path: str):
    """
    Create both a FAISS vectorstore and a BM25 index from the same chunks.
    Saves both to disk at index_path.
    
    Returns (vectorstore, bm25_index, chunks).
    """
    splitter = _build_splitter()
    chunks = splitter.split_documents(page_docs)
    
    # Build FAISS vectorstore
    vectorstore = FAISS.from_documents(chunks, get_embedder())
    vectorstore.save_local(index_path)
    
    # Build BM25 index over the same chunks
    bm25_index = BM25Index(chunks)
    save_bm25_index(bm25_index, index_path)
    
    return vectorstore, bm25_index, chunks


def load_hybrid_index(index_path: str):
    """
    Load both FAISS and BM25 indexes from disk.
    Returns (vectorstore, bm25_index). BM25 may be None if not found.
    """
    vectorstore = FAISS.load_local(index_path, get_embedder(), allow_dangerous_deserialization=True)
    bm25_index = load_bm25_index(index_path)
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
        print(f"Warning: Failed to save vectorstore for {session_id}: {err}")


def load_vectorstore_from_disk(session_id: str):
    try:
        session_dir = settings.VECTOR_CACHE_DIR / session_id
        if session_dir.exists():
            return FAISS.load_local(str(session_dir), get_embedder(), allow_dangerous_deserialization=True)
    except Exception as err:
        print(f"Warning: Could not load vectorstore for {session_id}: {err}")
    return None


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
    # FAISS semantic search (MMR for diversity)
    faiss_results = vectorstore.max_marginal_relevance_search(
        query,
        k=k,
        fetch_k=RETRIEVAL_FETCH_K,
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
