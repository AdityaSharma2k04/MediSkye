import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

_EMBEDDER_INSTANCE = None


def get_embedder():
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None:
        api_key = settings.GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY")
        _EMBEDDER_INSTANCE = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-2",
            google_api_key=api_key,
        )
    return _EMBEDDER_INSTANCE
