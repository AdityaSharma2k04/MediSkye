import os
import asyncio
import concurrent.futures
import logging
from langchain_core.embeddings import Embeddings
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

    def __init__(self, model: str = "models/gemini-embedding-2"):
        self.model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
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
        results = []
        for text in texts:
            emb = await self.aembed_query(text)
            results.append(emb)
        return results

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
        _EMBEDDER_INSTANCE = ResilientGeminiEmbeddings(model="models/gemini-embedding-2")
    return _EMBEDDER_INSTANCE
