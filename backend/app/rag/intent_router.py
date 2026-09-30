"""
Agentic Intent Router — classifies user queries before hitting the RAG pipeline.

Uses a fast, low-token Gemini call to determine query intent:
  - EMERGENCY:      Life-threatening symptoms → abort with emergency response
  - GENERAL_HEALTH: General medical question  → answer directly (no FAISS needed)
  - DOCUMENT_QA:    Question about their PDF  → route to Hybrid Search RAG

The keyword-based emergency check in safety.py runs first (zero API cost).
This router is the second gate — it catches edge cases the keywords miss and
intelligently skips FAISS for general questions to save latency and tokens.
"""

from enum import Enum
from google import genai
from app.core.config import settings


class QueryIntent(str, Enum):
    EMERGENCY = "EMERGENCY"
    GENERAL_HEALTH = "GENERAL_HEALTH"
    DOCUMENT_QA = "DOCUMENT_QA"


CLASSIFICATION_PROMPT = """You are a medical query classifier. Classify the user's query into EXACTLY ONE category.

Categories:
- EMERGENCY: The user describes an active, life-threatening situation (chest pain, stroke symptoms, severe bleeding, difficulty breathing, suicidal ideation, overdose, unconsciousness, seizure).
- GENERAL_HEALTH: The user asks a general medical or health question NOT specific to a personal lab report or uploaded document (e.g., "What causes high blood pressure?", "What is diabetes?", "How does cholesterol work?").
- DOCUMENT_QA: The user is asking about specific values, results, or findings in their uploaded medical report or PDF (e.g., "Is my hemoglobin normal?", "What does my LDL level mean?", "Summarize this report").

Rules:
- If the query references "my", "this report", "my results", specific lab values, or uploaded documents, classify as DOCUMENT_QA.
- If the query is educational or theoretical with no personal context, classify as GENERAL_HEALTH.
- When in doubt between GENERAL_HEALTH and DOCUMENT_QA, choose DOCUMENT_QA (safer — it will ground the answer in the report)

Respond with ONLY the category name, nothing else.

User query: {query}

Category:"""


async def classify_intent(query: str, has_document: bool = True) -> QueryIntent:
    """
    Classify user intent using a fast Gemini call.
    Falls back to DOCUMENT_QA on any error (safest default).

    Args:
        query: The user's query string.
        has_document: Whether the current session has a linked document.
                      If False, DOCUMENT_QA is always downgraded to GENERAL_HEALTH.
    """
    try:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=CLASSIFICATION_PROMPT.format(query=query),
            config={
                "temperature": 0.0,
                "max_output_tokens": 10,
            },
        )
        result = response.text.strip().upper()

        # Parse the response — handle variations
        if "EMERGENCY" in result:
            return QueryIntent.EMERGENCY
        elif "GENERAL_HEALTH" in result:
            return QueryIntent.GENERAL_HEALTH
        elif "DOCUMENT_QA" in result:
            # Downgrade to GENERAL_HEALTH if no document is present in session
            if not has_document:
                return QueryIntent.GENERAL_HEALTH
            return QueryIntent.DOCUMENT_QA
        else:
            # Unknown classification — default based on document availability
            if not has_document:
                return QueryIntent.GENERAL_HEALTH
            return QueryIntent.DOCUMENT_QA

    except Exception as e:
        print(f"Intent classification failed: {e}")
        # On error, fall back based on document availability
        return QueryIntent.DOCUMENT_QA if has_document else QueryIntent.GENERAL_HEALTH
