import os
import re
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent / "rag" / "prompts" / "fact_extraction.txt"


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    a = np.array(vec1, dtype=float)
    b = np.array(vec2, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _normalize_existing_facts(existing_facts: List[Any]) -> List[Dict[str, Any]]:
    normalized = []
    for f in existing_facts:
        if isinstance(f, dict):
            fid = str(f.get("id") or "")
            ftype = f.get("type") or f.get("fact_type") or ""
            ftext = f.get("text") or f.get("fact_text") or ""
        else:
            fid = str(getattr(f, "id", ""))
            ftype = getattr(f, "fact_type", "")
            ftext = getattr(f, "fact_text", "")
        if ftext:
            normalized.append({"id": fid, "type": ftype, "text": ftext})
    return normalized


def _format_conversation(messages: List[Any]) -> str:
    lines = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role", "User").capitalize()
            text = m.get("content") or m.get("message") or ""
        elif hasattr(m, "role") and hasattr(m, "message"):
            role = m.role.capitalize()
            text = m.message
        elif isinstance(m, str):
            role = "User"
            text = m
        else:
            role = "User"
            text = str(m)
        if text:
            lines.append(f"{role}: {text.strip()}")
    return "\n".join(lines)


async def extract_facts(
    messages: List[Any],
    existing_facts: List[Any],
    user_id: Any,
    dependent_id: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Extract durable patient facts and retractions from recent conversation messages using Gemini.
    Deduplicates newly extracted facts against existing facts of the same type via cosine similarity (> 0.85).
    """
    if not messages:
        return {"facts": [], "retractions": []}

    normalized_existing = _normalize_existing_facts(existing_facts)

    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as e:
        logger.error("Failed to read fact extraction prompt template: %s", e)
        return {"facts": [], "retractions": []}

    formatted_messages = _format_conversation(messages)
    if not formatted_messages.strip():
        return {"facts": [], "retractions": []}

    prompt = (
        template.replace("{existing_facts_json}", json.dumps(normalized_existing, indent=2))
        .replace("{messages}", formatted_messages)
    )

    extracted_data = {"facts": [], "retractions": []}
    try:
        from google import genai
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        response_text = response.text or ""

        # Extract JSON (handling markdown fences if returned)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            raw_json = json_match.group(1)
        else:
            raw_json = response_text.strip()

        extracted_data = json.loads(raw_json)
        if not isinstance(extracted_data, dict):
            logger.error("Extracted data is not a dictionary: %s", type(extracted_data))
            return {"facts": [], "retractions": []}

    except Exception as e:
        logger.error("Error calling Gemini or parsing JSON in fact extraction: %s", e)
        return {"facts": [], "retractions": []}

    raw_facts = extracted_data.get("facts", [])
    retractions = extracted_data.get("retractions", [])

    if not raw_facts:
        return {"facts": [], "retractions": retractions}

    # Deduplication against existing facts of same type
    filtered_facts = []
    
    # Pre-embed existing facts grouped by type if needed
    embedder = None
    try:
        from app.rag.embedder import get_embedder
        embedder = get_embedder()
    except Exception as e:
        logger.warning("Could not initialize embedder for fact deduplication: %s", e)

    for fact in raw_facts:
        fact_type = fact.get("type", "")
        fact_text = (fact.get("text") or "").strip()
        if not fact_text:
            continue

        # Look for existing facts of same type
        same_type_existing = [
            ef for ef in normalized_existing
            if ef.get("type", "").lower() == fact_type.lower()
        ]

        is_duplicate = False
        for ef in same_type_existing:
            ef_text = ef.get("text", "").strip()
            # Fast exact/case-insensitive match
            if fact_text.lower() == ef_text.lower():
                is_duplicate = True
                break

            # Semantic similarity check
            if embedder:
                try:
                    v1 = embedder.embed_query(fact_text)
                    v2 = embedder.embed_query(ef_text)
                    sim = _cosine_similarity(v1, v2)
                    if sim > 0.85:
                        is_duplicate = True
                        break
                except Exception as e:
                    logger.debug("Embedder similarity check failed: %s", e)

        if not is_duplicate:
            filtered_facts.append(fact)

    return {
        "facts": filtered_facts,
        "retractions": retractions,
    }
