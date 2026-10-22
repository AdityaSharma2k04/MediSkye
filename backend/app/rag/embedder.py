import os
import asyncio
import concurrent.futures
import logging
from typing import Optional
from langchain_core.embeddings import Embeddings
from app.core.config import settings
from app.llm.embeddings_client import embed_content_with_retry

logger = logging.getLogger(__name__)

_EMBEDDER_INSTANCE = None


def _run_coroutine_sync(coro):
    """Safely execute a coroutine from synchronous code whether a loop is active or not."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class ResilientGeminiEmbeddings(Embeddings):
    """LangChain-compatible Embeddings wrapper routing through embed_content_with_retry."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.resolved_embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            return _run_coroutine_sync(self.aembed_documents(texts))
        except Exception as e:
            logger.warning("aembed_documents sync runner failed; falling back to sequential embed_query: %s", e)
            results = []
            for text in texts:
                results.append(self.embed_query(text))
            return results

    def embed_query(self, text: str) -> list[float]:
        try:
            res = _run_coroutine_sync(embed_content_with_retry(contents=text, model=self.model))
            values = getattr(res, "embedding", None)
            if values and hasattr(values, "values"):
                return list(values.values)
            embeddings = getattr(res, "embeddings", None)
            if embeddings and len(embeddings) > 0 and hasattr(embeddings[0], "values"):
                return list(embeddings[0].values)
            return []
        except Exception as e:
            logger.error("Failed to generate embedding: %s", e)
            raise

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = 100
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                res = await embed_content_with_retry(contents=batch, model=self.model)
                embeddings = getattr(res, "embeddings", None)
                if embeddings and len(embeddings) == len(batch):
                    for emb in embeddings:
                        vals = getattr(emb, "values", None)
                        all_embeddings.append(list(vals) if vals is not None else [])
                    continue
                elif embeddings:
                    for emb in embeddings:
                        vals = getattr(emb, "values", None)
                        all_embeddings.append(list(vals) if vals is not None else [])
                    continue
                values = getattr(res, "embedding", None)
                if values and hasattr(values, "values") and len(batch) == 1:
                    all_embeddings.append(list(values.values))
                    continue
            except Exception as batch_err:
                logger.warning(
                    "Batch embedding call failed for %d items (%s); falling back to concurrent items: %s",
                    len(batch),
                    type(batch_err).__name__,
                    batch_err,
                )

            # Concurrent fallback if batch fails or returns unexpected format
            batch_results = await asyncio.gather(*[self.aembed_query(t) for t in batch])
            all_embeddings.extend(batch_results)

        return all_embeddings

    async def aembed_query(self, text: str) -> list[float]:
        try:
            res = await embed_content_with_retry(contents=text, model=self.model)
            values = getattr(res, "embedding", None)
            if values and hasattr(values, "values"):
                return list(values.values)
            embeddings = getattr(res, "embeddings", None)
            if embeddings and len(embeddings) > 0 and hasattr(embeddings[0], "values"):
                return list(embeddings[0].values)
            return []
        except Exception as e:
            logger.error("Failed to generate embedding: %s", e)
            raise


def get_embedder():
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        _EMBEDDER_INSTANCE = ResilientGeminiEmbeddings()
    return _EMBEDDER_INSTANCE
