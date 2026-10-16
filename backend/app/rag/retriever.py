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

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.rag.embedder import get_embedder
from app.rag.hybrid_search import BM25Index, save_bm25_index, load_bm25_index, reciprocal_rank_fusion
from app.core.config import settings

logger = logging.getLogger(__name__)

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
        if not db_doc.file_path or not os.path.exists(db_doc.file_path):
            continue
        try:
            vectorstore, bm25_index = load_hybrid_index(db_doc.file_path)
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


async def retrieve_relevant_chat_chunks(
    user_id,
    query: str,
    db,
    k: int = 3,
) -> list[Document]:
    """Retrieve relevant conversational memory from past chat sessions."""
    import re
    from sqlalchemy.future import select
    from app.db.models import ChatChunk

    try:
        res = await db.execute(
            select(ChatChunk)
            .filter(ChatChunk.user_id == user_id)
            .order_by(ChatChunk.created_at.desc())
            .limit(20)
        )
        chunks = res.scalars().all()
        if not chunks:
            return []

        query_words = set(re.findall(r"\w{3,}", query.lower()))
        scored_chunks = []
        for c in chunks:
            chunk_words = set(re.findall(r"\w{3,}", c.content.lower()))
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                scored_chunks.append((overlap, c))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [c for _, c in scored_chunks[:k]]

        docs = []
        for c in top_chunks:
            date_str = c.created_at.strftime("%Y-%m-%d") if c.created_at else "past"
            docs.append(Document(
                page_content=c.content,
                metadata={
                    "source": "chat_memory",
                    "summary": c.summary or "",
                    "created_at": date_str,
                }
            ))
        return docs
    except Exception as e:
        logger.error("Error retrieving chat chunks: %s", e)
        return []

