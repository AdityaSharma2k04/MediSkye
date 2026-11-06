import re
import json
import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np



logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent / "rag" / "prompts" / "fact_extraction.txt"

VALID_FACT_TYPES = {
    "condition", "medication", "allergy", "family_history",
    "symptom", "lifestyle", "measurement", "weight", "sport_hobby",
}
MAX_FACT_TEXT_LENGTH = 500


def _validate_extracted_facts(data: dict) -> dict:
    """Strip invalid facts and retractions before persistence."""
    if not isinstance(data, dict):
        return {"facts": [], "retractions": []}

    valid_facts = []
    for fact in data.get("facts", []):
        if not isinstance(fact, dict):
            continue
        text = (fact.get("text") or "").strip()
        ftype = (fact.get("type") or "").strip()
        if (
            ftype in VALID_FACT_TYPES
            and text
            and len(text) <= MAX_FACT_TEXT_LENGTH
            and "<" not in text  # Reject XML/HTML injection in stored facts
            and ">" not in text
        ):
            valid_facts.append(fact)

    valid_retractions = []
    for ret in data.get("retractions", []):
        if not isinstance(ret, dict):
            continue
        try:
            uuid.UUID(str(ret.get("existing_fact_id", "")))
            valid_retractions.append(ret)
        except (ValueError, TypeError):
            continue  # Skip malformed retraction IDs

    return {"facts": valid_facts, "retractions": valid_retractions}


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
    document_name: Optional[str] = None,
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

    from app.core.security import escape_xml_content
    doc_attr = f' document="{escape_xml_content(document_name)}"' if document_name else ""
    safe_messages = f"<conversation{doc_attr}>\n{escape_xml_content(formatted_messages)}\n</conversation>"
    prompt = (
        template.replace("{existing_facts_json}", json.dumps(normalized_existing, indent=2))
        .replace("{messages}", safe_messages)
    )

    try:
        from app.llm.gemini_client import call_gemini_with_retry, GeminiUnavailableError
        try:
            response = await call_gemini_with_retry(
                contents=prompt,
                user_id=user_id,
                config={"thinking_config": {"thinking_budget": 0}},
            )
            response_text = response.text or ""
        except GeminiUnavailableError as e:
            logger.warning("Skipping fact extraction — LLM unavailable: %s", e)
            return {"facts": [], "retractions": []}

        # Extract JSON (handling markdown fences if returned; take last match to counter user-injected blocks)
        json_matches = list(re.finditer(
            r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL
        ))
        if json_matches:
            raw_json = json_matches[-1].group(1)
        else:
            raw_json = response_text.strip()

        extracted_data = json.loads(raw_json)
        if not isinstance(extracted_data, dict):
            logger.error("Extracted data is not a dictionary: %s", type(extracted_data))
            return {"facts": [], "retractions": []}

        extracted_data = _validate_extracted_facts(extracted_data)

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

    # Collect unique texts needing embedding (only for facts that aren't already exact matches)
    texts_to_embed = set()
    for fact in raw_facts:
        fact_type = fact.get("type", "")
        fact_text = (fact.get("text") or "").strip()
        if not fact_text:
            continue

        same_type_existing = [
            ef for ef in normalized_existing
            if ef.get("type", "").lower() == fact_type.lower()
        ]
        has_exact_match = any(
            fact_text.lower() == (ef.get("text") or "").strip().lower()
            for ef in same_type_existing
        )
        if not has_exact_match and same_type_existing:
            texts_to_embed.add(fact_text)
            for ef in same_type_existing:
                ef_text = (ef.get("text") or "").strip()
                if ef_text:
                    texts_to_embed.add(ef_text)

    # Batch embed unique texts once to avoid N×M API calls
    embedding_cache: Dict[str, List[float]] = {}
    if embedder and texts_to_embed:
        try:
            unique_list = list(texts_to_embed)
            embeddings = await asyncio.to_thread(embedder.embed_documents, unique_list)
            for text, emb in zip(unique_list, embeddings):
                if emb:
                    embedding_cache[text] = emb
        except Exception as e:
            logger.warning(
                "Batch embedding for fact deduplication failed: %s; falling back to exact matching",
                e,
            )

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
        v1 = embedding_cache.get(fact_text)
        for ef in same_type_existing:
            ef_text = (ef.get("text") or "").strip()
            # Fast exact/case-insensitive match
            if fact_text.lower() == ef_text.lower():
                is_duplicate = True
                break

            # Semantic similarity check using cached embeddings
            if v1:
                v2 = embedding_cache.get(ef_text)
                if v2:
                    try:
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
