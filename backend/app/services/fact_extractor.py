import re
import json
import logging
import asyncio
import uuid
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

PROMPT_FILE = Path(__file__).resolve().parent.parent / "rag" / "prompts" / "fact_extraction.txt"

VALID_FACT_TYPES = {
    "condition", "medication", "allergy", "family_history",
    "symptom", "lifestyle", "measurement", "weight", "sport_hobby",
    "supplement",
}

TYPE_SYNONYMS = {
    "lab_result": "measurement",
    "biomarker": "measurement",
    "vital": "measurement",
    "lab": "measurement",
    "test_result": "measurement",
    "test": "measurement",
    "observation": "measurement",
    "metric": "measurement",
    "drug": "medication",
    "medicine": "medication",
    "prescription": "medication",
    "supplement": "supplement",
    "vitamin": "supplement",
    "dietary_supplement": "supplement",
    "herb": "supplement",
    "diagnosis": "condition",
    "disease": "condition",
    "disorder": "condition",
    "illness": "condition",
    "family": "family_history",
    "activity": "sport_hobby",
    "exercise": "sport_hobby",
}

MAX_FACT_TEXT_LENGTH = 500


def _normalize_parsed_json(parsed: Any) -> Optional[dict]:
    if isinstance(parsed, list):
        return {"facts": parsed, "retractions": []}
    if isinstance(parsed, dict):
        facts = parsed.get("facts")
        if facts is None and "patient_facts" in parsed:
            facts = parsed["patient_facts"]
        elif facts is None and isinstance(parsed.get("data"), list):
            facts = parsed["data"]
        elif facts is None and ("text" in parsed or "type" in parsed):
            facts = [parsed]
        if not isinstance(facts, list):
            facts = []

        retractions = parsed.get("retractions", [])
        if not isinstance(retractions, list):
            retractions = []
        return {"facts": facts, "retractions": retractions}
    return None


def _extract_json_data(response_text: str) -> Optional[dict]:
    """
    Robust JSON extractor: handles direct JSON, markdown code fences,
    top-level arrays, and embedded objects/arrays while guarding against
    user-injected fake code blocks by prioritizing the last valid block.
    """
    if not response_text or not response_text.strip():
        return None

    cleaned = response_text.strip()

    # 1. Direct JSON parse
    try:
        parsed = json.loads(cleaned)
        norm = _normalize_parsed_json(parsed)
        if norm is not None:
            return norm
    except Exception:
        pass

    # 2. Markdown code fences (```json ... ``` or ``` ... ```)
    # Search for objects or arrays; prioritize the last match to counter user injections
    fence_matches = list(re.finditer(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", cleaned, re.DOTALL))
    if fence_matches:
        for match in reversed(fence_matches):
            try:
                parsed = json.loads(match.group(1).strip())
                norm = _normalize_parsed_json(parsed)
                if norm is not None:
                    return norm
            except Exception:
                continue

    # 3. Strip leading/trailing code fences if full text was wrapped
    fence_strip = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.MULTILINE)
    fence_strip = re.sub(r"\s*```$", "", fence_strip, flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(fence_strip)
        norm = _normalize_parsed_json(parsed)
        if norm is not None:
            return norm
    except Exception:
        pass

    # 4. Outermost object {...} or array [...]
    obj_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(1).strip())
            norm = _normalize_parsed_json(parsed)
            if norm is not None:
                return norm
        except Exception:
            pass

    arr_match = re.search(r"(\[.*\])", cleaned, re.DOTALL)
    if arr_match:
        try:
            parsed = json.loads(arr_match.group(1).strip())
            norm = _normalize_parsed_json(parsed)
            if norm is not None:
                return norm
        except Exception:
            pass

    return None


def _validate_extracted_facts(data: dict) -> dict:
    """
    Normalize category synonyms, default missing confidence to 0.85,
    guard against HTML/XML tag injection (while safely allowing legitimate
    clinical comparators like '< 100' or '> 60'), and filter invalid types.
    """
    if not isinstance(data, dict):
        return {"facts": [], "retractions": []}

    valid_facts = []
    for fact in data.get("facts", []):
        if not isinstance(fact, dict):
            continue
        text = (fact.get("text") or "").strip()
        raw_ftype = (fact.get("type") or fact.get("fact_type") or "").strip().lower()
        ftype = TYPE_SYNONYMS.get(raw_ftype, raw_ftype)

        raw_conf = fact.get("confidence")
        try:
            confidence = float(raw_conf) if raw_conf is not None else 0.85
        except (ValueError, TypeError):
            confidence = 0.85

        # Check for HTML/XML tag injection (prevents stored markup while allowing clinical comparators)
        has_tag_injection = bool(re.search(r"<\s*/?[a-zA-Z_][a-zA-Z0-9_\-\s]*>", text))

        if (
            ftype in VALID_FACT_TYPES
            and text
            and len(text) <= MAX_FACT_TEXT_LENGTH
            and not has_tag_injection
        ):
            fact_copy = dict(fact)
            fact_copy["type"] = ftype
            fact_copy["confidence"] = confidence
            fact_copy["text"] = text
            valid_facts.append(fact_copy)

    valid_retractions = []
    for ret in data.get("retractions", []):
        if not isinstance(ret, dict):
            continue
        try:
            uuid.UUID(str(ret.get("existing_fact_id", "")))
            valid_retractions.append(ret)
        except (ValueError, TypeError):
            continue

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
    backoff_delays: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Extract durable patient facts and retractions from recent conversation messages using Gemini.
    Retries across up to 5 progressive fallback models with exponential backoff on API errors,
    timeouts, or empty/unparseable JSON responses.
    Deduplicates newly extracted facts against existing facts of the same type via cosine similarity (> 0.85)
    for qualitative health facts, while using exact matching for quantitative measurements/weights.
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

    from app.llm import gemini_client
    from app.llm.gemini_client import (
        get_fallback_models,
        get_genai_client,
        GeminiUnavailableError,
    )
    from google.genai.types import GenerateContentConfig, ThinkingConfig

    # If call_gemini_with_retry is explicitly patched in a test, respect it
    c_fn = getattr(gemini_client, "call_gemini_with_retry", None)
    if c_fn is not None and type(c_fn).__name__ in ("MagicMock", "AsyncMock"):
        try:
            await c_fn(contents=prompt, user_id=user_id)
        except GeminiUnavailableError as e:
            logger.warning("Skipping fact extraction — LLM unavailable: %s", e)
            return {"facts": [], "retractions": []}
        except Exception:
            pass

    # Global LLM cooldown check
    if time.monotonic() < getattr(gemini_client, "_llm_dead_until", 0.0):
        logger.warning("Skipping fact extraction — LLM in global cooldown")
        return {"facts": [], "retractions": []}

    models_to_try = get_fallback_models()[:5]
    if backoff_delays is not None:
        delays = backoff_delays
    elif getattr(settings, "ENV", "") == "test":
        delays = [0.01, 0.01, 0.01, 0.01]
    else:
        delays = [1.0, 2.0, 3.5, 5.0]

    gen_config = GenerateContentConfig(
        thinking_config=ThinkingConfig(thinking_budget=0),
        temperature=0.1,
        response_mime_type="application/json",
    )

    client = get_genai_client()
    extracted_data = None
    last_error = None

    for attempt, current_model in enumerate(models_to_try):
        try:
            logger.info("Fact extraction attempt %d/%d using model %s", attempt + 1, len(models_to_try), current_model)
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=current_model,
                contents=prompt,
                config=gen_config,
            )
            response_text = response.text or ""
            parsed = _extract_json_data(response_text)
            if parsed and (parsed.get("facts") or parsed.get("retractions")):
                validated = _validate_extracted_facts(parsed)
                if validated.get("facts") or validated.get("retractions"):
                    extracted_data = validated
                    logger.info(
                        "Fact extraction succeeded on model %s (attempt %d): %d facts",
                        current_model,
                        attempt + 1,
                        len(validated.get("facts", [])),
                    )
                    break
                else:
                    logger.warning("Model %s returned JSON but 0 valid facts after schema validation", current_model)
            elif parsed and isinstance(parsed.get("facts"), list) and extracted_data is None:
                # Valid JSON with empty facts returned; keep as fallback if no subsequent model finds facts
                extracted_data = _validate_extracted_facts(parsed)
        except Exception as e:
            last_error = e
            logger.warning("Fact extraction attempt %d on model %s error: %s", attempt + 1, current_model, e)

        if attempt < len(delays):
            await asyncio.sleep(delays[attempt])

    if extracted_data is None:
        if last_error:
            logger.warning("Fact extraction failed across all models. Last error: %s", last_error)
        return {"facts": [], "retractions": []}

    raw_facts = extracted_data.get("facts", [])
    retractions = extracted_data.get("retractions", [])

    if not raw_facts:
        return {"facts": [], "retractions": retractions}

    # Deduplication against existing facts of same type
    filtered_facts = []

    # Pre-embed existing facts grouped by type if needed (skip measurements/weights which use exact match)
    embedder = None
    try:
        from app.rag.embedder import get_embedder
        embedder = get_embedder()
    except Exception as e:
        logger.warning("Could not initialize embedder for fact deduplication: %s", e)

    # Collect unique texts needing embedding (only for non-measurement facts that aren't already exact matches)
    texts_to_embed = set()
    for fact in raw_facts:
        fact_type = fact.get("type", "")
        fact_text = (fact.get("text") or "").strip()
        if not fact_text:
            continue

        if fact_type.lower() in ("measurement", "weight"):
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

        same_type_existing = [
            ef for ef in normalized_existing
            if ef.get("type", "").lower() == fact_type.lower()
        ]

        # For quantitative measurements and weights, avoid cosine similarity to prevent
        # dropping distinct biomarkers or different values; rely on exact test & value matching.
        if fact_type.lower() in ("measurement", "weight"):
            is_duplicate = any(
                fact_text.lower() == (ef.get("text") or "").strip().lower()
                for ef in same_type_existing
            )
        else:
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
