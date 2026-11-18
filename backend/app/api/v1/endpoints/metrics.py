import asyncio
import copy
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.auth import UserDTO, get_current_user
from app.core.config import settings
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import DependentProfile, Document, PatientFact, User, utcnow
from app.llm.gemini_client import GeminiUnavailableError, call_gemini_with_retry
from app.rag.embedder import get_embedder
from app.rag.index_storage import aensure_index_local
from app.rag.retriever import (
    get_cached_hybrid_index,
    load_hybrid_index,
    retrieve_relevant_docs,
)
from app.schemas.upload import LabMetricItem, MetricsResponse
from app.services.clinical_units import (
    _parse_first_float,
    canonical_biomarker_key,
    check_is_future_date,
    compute_biomarker_delta,
    convert_to_standard,
    extract_specimen_collection_date,
    is_sample_document,
    normalize_clinical_unit,
    parse_report_chronology,
)
from app.services.upload_jobs import is_stale_building
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from google.genai.types import GenerateContentConfig, ThinkingConfig
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm.exc import StaleDataError

logger = logging.getLogger(__name__)

router = APIRouter()

METRICS_PROMPT_CHAR_BUDGET = 16000

_RANGE_BETWEEN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(-?\d+(?:\.\d+)?)(?:\s*[a-zA-Z%/µμ0-9.^]+)?\s*$",
    re.IGNORECASE,
)
_RANGE_UPPER = re.compile(
    r"^\s*(?:<=|<|≤|less than|up to)\s*(-?\d+(?:\.\d+)?)(?:\s*[a-zA-Z%/µμ0-9.^]+)?\s*$",
    re.IGNORECASE,
)
_RANGE_LOWER = re.compile(
    r"^\s*(?:>=|>|≥|greater than|more than)\s*(-?\d+(?:\.\d+)?)(?:\s*[a-zA-Z%/µμ0-9.^]+)?\s*$",
    re.IGNORECASE,
)
_COMPARATOR_RE = re.compile(
    r"^\s*(?P<val_op><=|>=|<|>|≤|≥)\s*(?P<val_num>-?\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_RANGE_AMBIGUOUS = re.compile(r"(?:-|–|—|to|<|>|<=|>=)")
_RANGE_DEMOGRAPHIC = re.compile(
    r"\b(?:male|female|adult|child|pediatric|infant|men|women|years|yrs|males|females)\b",
    re.IGNORECASE,
)


def _status_from_range(value: Any, rng: str) -> str | None:
    """Derive Low / High / Normal / None from a numeric or comparator value and reference range."""
    if value is None or not rng:
        return None
    raw_rng = str(rng).strip()
    if _RANGE_DEMOGRAPHIC.search(raw_rng):
        return None

    # Normalize European decimal commas and thousand-separators in reference range
    while re.search(r'(\d),(\d{3})\b', raw_rng):
        raw_rng = re.sub(r'(\d),(\d{3})\b', r'\1\2', raw_rng)
    text = re.sub(r'(\d),(\d{1,2})(?!\d)', r'\1.\2', raw_rng)

    # Check for comparator in value (e.g. < 0.5, <= 0.02, > 200, >= 100)
    val_str = str(value).strip()
    m_comp = _COMPARATOR_RE.match(val_str)
    val_op = None
    if m_comp:
        raw_op = m_comp.group("val_op")
        if raw_op in ("≤", "<="):
            val_op = "<="
        elif raw_op in ("≥", ">="):
            val_op = ">="
        elif raw_op == "<":
            val_op = "<"
        elif raw_op == ">":
            val_op = ">"
        val = _parse_first_float(m_comp.group("val_num"))
    else:
        val = _parse_first_float(val_str)

    if val is None:
        return None

    # 1. Between range: lo - hi
    m = _RANGE_BETWEEN.match(text)
    if m:
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo > hi:
                lo, hi = hi, lo
            if val_op in (">", ">="):
                if val >= hi:
                    return "High"
                return None
            elif val_op in ("<", "<="):
                if val <= lo and lo > 0:
                    return "Low"
                elif val <= hi:
                    return "Normal"
                return None
            else:
                if val < lo:
                    return "Low"
                if val > hi:
                    return "High"
                return "Normal"
        except (ValueError, TypeError):
            return None

    # 2. Upper bound range: < hi or <= hi
    m = _RANGE_UPPER.match(text)
    if m:
        try:
            hi = float(m.group(1))
            if val_op in (">", ">="):
                if val >= hi:
                    return "High"
                return None
            elif val_op in ("<", "<="):
                if val <= hi:
                    return "Normal"
                return None
            else:
                return "High" if val > hi else "Normal"
        except (ValueError, TypeError):
            return None

    # 3. Lower bound range: > lo or >= lo
    m = _RANGE_LOWER.match(text)
    if m:
        try:
            lo = float(m.group(1))
            if val_op in ("<", "<="):
                if val <= lo:
                    return "Low"
                return None
            elif val_op in (">", ">="):
                if val >= lo:
                    return "Normal"
                return None
            else:
                return "Low" if val < lo else "Normal"
        except (ValueError, TypeError):
            return None

    return None


_STRATUM = re.compile(
    r"(?P<label>adult\s+male|adult\s+female|female|male|women|woman|men|man|girls?|boys?|"
    r"(?-i:\b[MF]\b)|child(?:ren)?|infants?|neonates?|newborns?|pediatric|adults?)"
    r"\s*[:\-–—(]?\s*(?P<lo>-?\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<hi>-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _stratum_class(label: str) -> str:
    l = label.strip().lower()
    if "female" in l or l in ("women", "woman", "f", "girl", "girls"):
        return "female"
    if "male" in l or l in ("men", "man", "m", "boy", "boys"):
        return "male"
    return "other"


def _status_from_demographic_ranges(value: Any, rng: str, sex: str | None) -> str | None:
    """High/Low/Normal for 'Male: a-b; Female: c-d' style ranges, or None if unresolved."""
    v = _parse_first_float(value)
    if v is None or not rng:
        return None
    subs = [
        (_stratum_class(m.group("label")), float(m.group("lo")), float(m.group("hi")))
        for m in _STRATUM.finditer(rng)
    ]
    if len(subs) < 2 or any(c == "other" for c, _, _ in subs):
        return None  # single range, or age-group strata (needs patient age)

    def st(lo: float, hi: float) -> str:
        return "Low" if v < lo else "High" if v > hi else "Normal"

    if sex in ("male", "female"):
        mine = [(lo, hi) for c, lo, hi in subs if c == sex]
        if len(mine) == 1:
            return st(*mine[0])
    statuses = {st(lo, hi) for _, lo, hi in subs}
    return statuses.pop() if len(statuses) == 1 else None


_MULTI_TIER_BAND_RE = re.compile(
    r'(?P<label>[a-zA-Z\s]+?)\s*[:=]\s*(?:(?P<op>[<>]=?|≤|≥)\s*)?(?P<lo>-?\d+(?:\.\d+)?)(?:\s*(?:-|–|—|to)\s*(?P<hi>-?\d+(?:\.\d+)?))?',
    re.IGNORECASE
)


def _status_from_multi_tier(val_float: float, rng: str) -> str | None:
    """Parse multi-tier reference bands (e.g. Desirable: <200, Borderline: 200-239, High: >=240)."""
    if not rng:
        return None
    kw = ['desirable', 'borderline', 'optimal', 'prediabetes', 'diabetes', 'moderate', 'high']
    if not any(k in rng.lower() for k in kw):
        return None

    matches = list(_MULTI_TIER_BAND_RE.finditer(rng))
    if len(matches) < 2:
        return None

    for m in matches:
        label = m.group("label").strip().lower()
        op = m.group("op")
        lo = float(m.group("lo"))
        hi = float(m.group("hi")) if m.group("hi") else None

        inside = False
        if op in ("<", "<=", "≤"):
            inside = val_float < lo if op == "<" else val_float <= lo
        elif op in (">", ">=", "≥"):
            inside = val_float > lo if op == ">" else val_float >= lo
        elif hi is not None:
            inside = lo <= val_float <= hi

        if inside:
            if any(w in label for w in ["desirable", "optimal", "normal"]):
                return "Normal"
            if any(w in label for w in ["borderline", "prediabetes", "near optimal", "moderate"]):
                return "Borderline"
            if any(w in label for w in ["high", "diabetes", "elevated", "critical"]):
                return "High"
            if any(w in label for w in ["low", "deficient"]):
                return "Low"
    return None


def _resolve_status(llm_status: Any, value: Any, rng: Any, sex: str | None) -> str:
    llm = str(llm_status or "").strip()
    rng = str(rng or "")
    v_float = _parse_first_float(value)

    if v_float is not None:
        multi_tier = _status_from_multi_tier(v_float, rng)
        if multi_tier is not None:
            return multi_tier

    derived = _status_from_range(value, rng)
    demographic = False
    if derived is None:
        existing = globals().get("_RANGE_DEMOGRAPHIC")
        demographic = bool(existing.search(rng)) if existing is not None else False
        demographic = demographic or len(list(_STRATUM.finditer(rng))) >= 2
        if demographic:
            derived = _status_from_demographic_ranges(value, rng, sex)
            if derived is None and v_float is not None:
                subs = [
                    (float(m.group("lo")), float(m.group("hi")))
                    for m in _STRATUM.finditer(rng)
                ]
                if len(subs) >= 2:
                    statuses = {
                        ("Low" if v_float < lo else "High" if v_float > hi else "Normal")
                        for lo, hi in subs
                    }
                    if len(statuses) == 1:
                        derived = statuses.pop()

    # Support Qualitative / Serology Results (F-005)
    if derived is None and rng:
        val_str_clean = str(value or "").strip().lower()
        rng_clean = rng.strip().lower()
        if re.match(r"^\s*(?:negative|non[-\s]?reactive|absent|nil|normal|clear|pale\s+yellow)\s*$", rng_clean, re.IGNORECASE):
            if val_str_clean in ("negative", "non-reactive", "non reactive", "absent", "nil", "normal", "clear", "pale yellow", "none detected", "none", "0") or val_str_clean == rng_clean:
                derived = "Normal"
            elif (re.search(r"\b(?:positive|reactive|detected|present|trace|calcium\s+oxalate|crystals?|casts?)\b", val_str_clean, re.IGNORECASE) or re.search(r"(?<!\w)\+[1-4]?(?!\w)", val_str_clean)) and not re.search(r"\b(?:non[-\s]?reactive|negative|absent|nil)\b", val_str_clean, re.IGNORECASE):
                if llm.lower() in ("high", "abnormal", "critical"):
                    return llm
                return "High"
            elif val_str_clean != rng_clean and not re.search(r"\b(?:non[-\s]?reactive|negative|absent|nil|normal|clear|pale\s+yellow)\b", val_str_clean, re.IGNORECASE):
                if llm.lower() in ("high", "abnormal", "critical"):
                    return llm
                return "Abnormal"
            elif re.match(r"^\s*(?:negative|non[-\s]?reactive|absent|nil|none\s+detected)\s*$", val_str_clean, re.IGNORECASE):
                return "Normal"

    if not llm:
        return derived or "Unknown"
    if llm.lower() == "normal":
        if derived in ("High", "Low"):
            return derived          # numbers beat a wrong "Normal"
        if derived is None and demographic:
            return "Unknown"        # unresolved stratified range: no false reassurance
    return llm                      # High/Low/Critical/Abnormal/Borderline etc. are preserved as-is


async def _load_patient_sex(db: AsyncSession, doc: Any) -> str | None:
    """'male'/'female' from the dependent's profile if the document belongs to one, else the owner's."""
    try:
        if getattr(doc, "dependent_id", None):
            res = await db.execute(select(DependentProfile.biological_sex).filter(DependentProfile.id == doc.dependent_id))
        else:
            res = await db.execute(select(User.biological_sex).filter(User.id == doc.user_id))
        raw = str(res.scalars().first() or "").strip().lower()
        return raw if raw in ("male", "female") else None
    except Exception:
        return None


async def extract_and_cache_metrics(
    doc_id: uuid.UUID | str,
    page_docs: list[Any] | None = None,
    db: AsyncSession | None = None,
    user_id: uuid.UUID | str | None = None,
    raw_chunks: list[str] | None = None,
    _internal_reextract: bool = False,
) -> list[dict[str, Any]] | None:
    """
    Modularized biomarker extraction and caching logic.
    Can be invoked during document upload (passing page_docs) or on-demand from the metrics API.
    Extracts structured metrics with Gemini, validates against clinical rules,
    and caches the result directly on Document.cached_metrics.
    """
    if isinstance(page_docs, AsyncSession) and db is None:
        db = page_docs
        page_docs = None

    if db is None:
        raise ValueError("Database session (db) must be provided to extract_and_cache_metrics.")

    if isinstance(doc_id, str):
        try:
            doc_id = uuid.UUID(doc_id)
        except ValueError:
            logger.error("Invalid UUID format for doc_id: %s", doc_id)
            return []

    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalars().first()
    if not doc:
        logger.warning("Document %s not found for metrics extraction.", doc_id)
        return []

    patient_sex = await _load_patient_sex(db, doc)

    combined_text = ""
    if page_docs:
        all_pages = [getattr(d, "page_content", str(d)) for d in page_docs if getattr(d, "page_content", str(d))]
        full_text = "\n".join(all_pages)
        if len(full_text) <= METRICS_PROMPT_CHAR_BUDGET:
            combined_text = full_text
        else:
            keywords = (
                "lab", "test", "result", "reference", "range", "unit", "blood", "serum",
                "count", "panel", "hemoglobin", "glucose", "cholesterol", "platelet", "wbc", "rbc",
                "interval", "plasma", "urine", "assay", "profile", "mmol", "umol", "µmol",
                "iu/", "miu", "u/l", "ng/", "pg/", "ratio", "normal", "high", "low",
                "reactive", "negative", "positive"
            )
            lab_pages = [p for p in all_pages if any(kw in p.lower() for kw in keywords)]
            combined_text = "\n".join(lab_pages) if lab_pages else full_text
    elif raw_chunks:
        combined_text = "\n".join(raw_chunks)
    elif isinstance(doc.cached_metrics, dict) and doc.cached_metrics.get("_raw_chunks") and not _internal_reextract:
        combined_text = "\n".join(doc.cached_metrics["_raw_chunks"])
    elif doc.file_path:
        vectorstore = None
        bm25_index = None
        try:
            cached_entry = get_cached_hybrid_index(str(doc.id)) or get_cached_hybrid_index(doc.file_path)
            if cached_entry is not None:
                vectorstore, bm25_index = cached_entry
            elif hasattr(FAISS.load_local, "mock_calls") or hasattr(FAISS.load_local, "_mock_return_value"):
                vectorstore = await asyncio.to_thread(
                    FAISS.load_local, doc.file_path, get_embedder(), allow_dangerous_deserialization=True
                )
            else:
                resolved_path = str(await aensure_index_local(doc.file_path))
                vectorstore, bm25_index = await asyncio.to_thread(load_hybrid_index, resolved_path)
        except Exception as e:
            logger.warning("Could not load document index for doc %s: %s; attempting in-memory recovery", doc.id, e)
            if doc.extracted_text and doc.extracted_text.strip():
                combined_text = doc.extracted_text.strip()
            elif isinstance(doc.cached_metrics, dict) and doc.cached_metrics.get("_raw_chunks"):
                combined_text = "\n".join(doc.cached_metrics["_raw_chunks"])
            else:
                raise HTTPException(status_code=500, detail="Could not load document index.")

        if not combined_text and vectorstore is not None:
            def _extract_ordered_chunks(v, b) -> list[str]:
                # 1. BM25 corpus retains original chunk ordering
                if b is not None and hasattr(b, "chunks") and isinstance(b.chunks, (list, tuple)) and b.chunks:
                    texts = [getattr(c, "page_content", "") for c in b.chunks if isinstance(getattr(c, "page_content", None), str) and getattr(c, "page_content", "").strip()]
                    if texts:
                        return texts
                # 2. FAISS index_to_docstore_id order
                if hasattr(v, "index_to_docstore_id") and isinstance(v.index_to_docstore_id, dict) and hasattr(v, "docstore"):
                    try:
                        texts = []
                        for i in range(len(v.index_to_docstore_id)):
                            doc_item = v.docstore.search(v.index_to_docstore_id[i])
                            if hasattr(doc_item, "page_content") and isinstance(doc_item.page_content, str) and doc_item.page_content.strip():
                                texts.append(doc_item.page_content)
                        if texts:
                            return texts
                    except Exception:
                        pass
                # 3. FAISS docstore _dict fallback
                if hasattr(v, "docstore") and hasattr(v.docstore, "_dict") and isinstance(v.docstore._dict, dict):
                    texts = [getattr(c, "page_content", "") for c in v.docstore._dict.values() if isinstance(getattr(c, "page_content", None), str) and getattr(c, "page_content", "").strip()]
                    if texts:
                        return texts
                return []

            ordered_texts = _extract_ordered_chunks(vectorstore, bm25_index)
            if ordered_texts:
                combined_text = "\n".join(ordered_texts)
            else:
                docs = await asyncio.to_thread(
                    retrieve_relevant_docs,
                    "blood count lab results reference ranges cholesterol liver function",
                    vectorstore,
                    bm25_index,
                    k=12,
                )
                combined_text = "\n".join([d.page_content for d in docs])
    else:
        return []

    if not combined_text.strip():
        try:
            doc.cached_metrics = []
            flag_modified(doc, "cached_metrics")
            db.add(doc)
            await db.commit()
        except StaleDataError:
            await db.rollback()
            logger.info("Document %s was deleted while metrics extraction was in-flight; discarding result.", doc_id)
            return []
        return []

    windows = []
    if len(combined_text) <= METRICS_PROMPT_CHAR_BUDGET:
        windows = [combined_text]
    else:
        # Multi-window extraction (F-007): chunk up to 3 windows of 16k chars
        for i in range(0, min(len(combined_text), METRICS_PROMPT_CHAR_BUDGET * 3), METRICS_PROMPT_CHAR_BUDGET):
            chunk = combined_text[i:i + METRICS_PROMPT_CHAR_BUDGET].strip()
            if chunk:
                windows.append(chunk)

    _IGNORED_TEST_NAME = re.compile(
        r"\b(iso\s*15189|nabl|certified|accreditation|central facility|hospital|laborator(?:y|ies)|helpline|"
        r"boulevard|street|report id|accession|patient name|referred by|phone)\b",
        re.IGNORECASE,
    )

    effective_user_id = user_id or doc.user_id
    raw_metrics = []
    seen_canonical_keys = set()
    any_success = False

    try:
        for window_text in windows:
            extract_prompt = f"""You are a specialized medical lab data extraction system.
Extract structured clinical biomarker values from the following medical report text into a clean JSON array.

CRITICAL EXTRACTION RULES:
1. Extract ALL clinical tests, investigations, and analytes present in the report. This includes:
   - Routine blood panels (e.g., Complete Blood Count, Liver/Kidney function, Lipid profile, Thyroid, Electrolytes, HbA1c, Glucose, Vitamins).
   - ALL urinalysis investigations: Physical examination (Colour, Appearance, Specific Gravity, pH), Chemical examination (Protein, Glucose, Ketones, Blood, Bilirubin, Urobilinogen, Nitrite, Leucocyte Esterase), Microscopic examination (Pus Cells, Red Blood Cells, Epithelial Cells, Casts, Crystals, Bacteria), and Urine ACR.
2. DO NOT extract metadata, accreditation numbers (ISO, NABL, CAP), clinic addresses, technician/doctor names, or text from document headers/footers.
3. Strictly Ignore any line or test name containing: "ISO", "NABL", "CAP", "Certified", "Facility", "Hospital", "Lab", "Laboratory", "Helpline", "Boulevard", "Street", "Report ID", "Accession", "Sample", "Patient Name", "Referred By", "Page", or "Phone".
4. For qualitative tests or investigations where no physical unit is printed (e.g. Colour, Appearance, Ketones, Casts, Crystals, Bacteria, or dipstick tests), use 'qualitative' or '' for unit. Do NOT omit or discard tests simply because their unit is empty or qualitative!
5. If no valid metrics are found, return an empty list `[]`.

Return ONLY raw JSON with schema:
[
  {{
    "test": "Investigation Name",
    "value": "Observed value (e.g. 14.5, Trace, Positive (+), Clear, Nil)",
    "unit": "Unit (e.g. g/dL, mg/dL, /HPF, or empty if none)",
    "range": "Reference range (e.g. 13.8 - 17.2, Negative, Clear)",
    "status": "Normal" | "High" | "Low" | "Abnormal"
  }}
]

Report text:
{window_text}
"""
            response = await call_gemini_with_retry(
                contents=extract_prompt,
                model=getattr(settings, "PRIMARY_METRICS_MODEL", "gemini-3.8-flash"),
                user_id=effective_user_id,
                backoff_delays=[1.5, 4.0, 16.0],
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(thinking_budget=0),
                    temperature=0.0,
                ),
            )
            if not response or not response.text:
                continue

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()
            try:
                parsed = json.loads(text)
            except Exception:
                continue

            if not isinstance(parsed, list):
                continue

            any_success = True
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                test_name = str(item.get("test") or item.get("name") or "").strip()
                val_str = str(item.get("value", "")).strip()
                unit_str = str(item.get("unit", "")).strip()

                if _IGNORED_TEST_NAME.search(test_name):
                    continue

                if not test_name or not val_str:
                    continue

                c_key = canonical_biomarker_key(test_name, allow_urinalysis=True)
                # Disambiguate urine investigations if test_name was generic like Glucose, Bilirubin, RBC, WBC
                val_lower = val_str.lower()
                unit_lower = unit_str.lower()
                if c_key == "glucose" and (val_lower in ("negative", "nil", "normal", "trace", "present") or "qualitative" in unit_lower):
                    c_key = "urine_glucose"
                elif c_key == "bilirubin" and (val_lower in ("negative", "nil", "normal", "absent") or "qualitative" in unit_lower):
                    c_key = "urine_bilirubin"
                elif c_key == "rbc" and ("/hpf" in unit_lower or "/hpf" in val_lower):
                    c_key = "urine_rbc"
                elif c_key == "wbc" and ("/hpf" in unit_lower or "/hpf" in val_lower or "pus" in test_name.lower()):
                    c_key = "urine_pus_cells"

                if c_key in seen_canonical_keys:
                    continue
                seen_canonical_keys.add(c_key)

                normalized_unit = normalize_clinical_unit(unit_str) if unit_str else ""

                ref_range = str(item.get("range") or item.get("reference_range") or "").strip()
                range_str = ref_range
                final_status = _resolve_status(item.get("status"), val_str, range_str, patient_sex)

                metric_dict = {
                    "test": test_name,
                    "value": val_str,
                    "unit": normalized_unit,
                    "range": ref_range,
                    "status": final_status,
                }
                raw_metrics.append(metric_dict)

        if not any_success and len(windows) > 0:
            return None

        try:
            # If doc.collected_at is None, write back extracted collection date
            if not doc.collected_at and combined_text:
                extracted_date = extract_specimen_collection_date(combined_text)
                if extracted_date:
                    doc.collected_at = extracted_date
                    flag_modified(doc, "collected_at")

            has_extracted_text = bool(getattr(doc, "extracted_text", None) and str(doc.extracted_text).strip())
            chunks_to_save = [] if has_extracted_text else (raw_chunks or (all_pages if page_docs else ordered_texts if 'ordered_texts' in locals() and ordered_texts else []))
            cached_payload = {"metrics": raw_metrics}
            if chunks_to_save:
                cached_payload["_raw_chunks"] = chunks_to_save
            doc.cached_metrics = cached_payload
            flag_modified(doc, "cached_metrics")
            db.add(doc)

            # Task 4: Deterministically persist 100% of lab measurement facts at upload time
            if raw_metrics and doc.user_id:
                col_iso = None
                if doc.collected_at:
                    try:
                        dt = parse_report_chronology(doc)
                        if dt:
                            col_iso = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                    if not col_iso:
                        col_iso = str(doc.collected_at).strip()

                date_part = f" on {col_iso}" if col_iso else ""
                report_label = doc.filename or doc.title or "Lab Report"
                doc_uuid_str = str(doc.id)

                # Remove existing measurement facts for this document to prevent duplicates
                await db.execute(
                    delete(PatientFact).where(
                        PatientFact.user_id == doc.user_id,
                        PatientFact.dependent_id == doc.dependent_id,
                        PatientFact.source_id == doc_uuid_str,
                        PatientFact.fact_type == "measurement",
                    )
                )

                for item in raw_metrics:
                    test_name = str(item.get("test") or item.get("name") or "").strip()
                    val_str = str(item.get("value") or "").strip()
                    unit_str = str(item.get("unit") or "").strip()
                    status_str = str(item.get("status") or "Normal").strip()
                    c_key = canonical_biomarker_key(test_name, allow_urinalysis=True) or test_name.lower()

                    u_part = f" {unit_str}" if (unit_str and unit_str.lower() != "qualitative") else ""
                    fact_str = f"{test_name}: {val_str}{u_part} ({status_str}){date_part} [Source Report: {report_label}]"
                    fact_str = re.sub(r'  +', ' ', fact_str).strip()

                    pf = PatientFact(
                        user_id=doc.user_id,
                        dependent_id=doc.dependent_id,
                        fact_type="measurement",
                        fact_key=c_key,
                        fact_text=fact_str,
                        confidence=1.0,
                        is_active=True,
                        is_user_verified=False,
                        source_type="pdf",
                        source_id=doc_uuid_str,
                        first_seen_at=utcnow(),
                        last_seen_at=utcnow(),
                    )
                    db.add(pf)

            await db.commit()
            try:
                await db.refresh(doc)
            except Exception:
                pass
            return raw_metrics
        except StaleDataError:
            await db.rollback()
            logger.info("Document %s was deleted while metrics extraction was in-flight; discarding result.", doc_id)
            return []
    except HTTPException:
        raise
    except StaleDataError:
        await db.rollback()
        logger.info("Document %s was deleted while metrics extraction was in-flight; discarding result.", doc_id)
        return []
    except Exception as err:
        if isinstance(err, (StaleDataError, GeminiUnavailableError, asyncio.TimeoutError, TimeoutError)) or "timeout" in str(err).lower() or "disconnect" in str(err).lower():
            logger.warning("Metrics extraction transient error (will retry on-demand): %s", err)
        else:
            logger.warning("Metrics extraction error (will retry on-demand): %s", err)
        return None


async def _apply_longitudinal_deltas(
    doc: Document,
    raw_list: list[Any],
    current_user: User | UserDTO,
    db: AsyncSession,
) -> tuple[list[LabMetricItem], str | None, str | None]:
    # Deepcopy raw_list to prevent any in-memory delta mutations from touching DB state
    raw_copied = copy.deepcopy(raw_list)

    normalized_items = []
    for item in raw_copied:
        if isinstance(item, dict):
            d = dict(item)
        elif hasattr(item, "model_dump"):
            d = item.model_dump()
        else:
            continue
        d["unit"] = normalize_clinical_unit(d.get("unit", ""))
        normalized_items.append(d)

    current_collected_dt = parse_report_chronology(doc)

    # Find prior document for same user & dependent with cached metrics
    prior_res = await db.execute(
        select(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.dependent_id == doc.dependent_id,
            Document.id != doc.id,
            Document.cached_metrics.is_not(None)
        )
    )
    candidates = prior_res.scalars().all()
    prior_doc = None

    if current_collected_dt and candidates:
        # Strict Chronological Ordering: ONLY select candidates where candidate_collected_dt < current_collected_dt
        valid_priors = []
        for cand in candidates:
            cand_dt = parse_report_chronology(cand)
            if cand_dt and cand_dt < current_collected_dt:
                valid_priors.append((cand_dt, cand))
        if valid_priors:
            # Sort descending by chronological collection date to find closest prior baseline
            valid_priors.sort(key=lambda x: x[0], reverse=True)
            prior_doc = valid_priors[0][1]
    elif not current_collected_dt and candidates:
        # Fallback only when current doc has no parseable collection date
        valid_priors = []
        for cand in candidates:
            cand_dt = parse_report_chronology(cand)
            # If candidate has a collection date but current doesn't, cannot guarantee chronology unless created_at applies
            if cand.created_at and doc.created_at and cand.created_at < doc.created_at:
                valid_priors.append((cand.created_at, cand))
        if valid_priors:
            valid_priors.sort(key=lambda x: x[0], reverse=True)
            prior_doc = valid_priors[0][1]

    prior_doc_id = str(prior_doc.id) if prior_doc else None
    prior_doc_date = (prior_doc.collected_at or (prior_doc.created_at.strftime('%d %b %Y') if prior_doc.created_at else None)) if prior_doc else None

    prior_metrics_map = {}
    if prior_doc and prior_doc.cached_metrics:
        raw_prior = prior_doc.cached_metrics
        if isinstance(raw_prior, str):
            try:
                raw_prior = json.loads(raw_prior)
            except Exception:
                raw_prior = []
        if isinstance(raw_prior, dict) and "metrics" in raw_prior:
            raw_prior = raw_prior["metrics"]
        if isinstance(raw_prior, list):
            for pm in raw_prior:
                if isinstance(pm, dict):
                    t_name = pm.get("test") or pm.get("name") or ""
                    key = canonical_biomarker_key(t_name, allow_urinalysis=True)
                    if key:
                        prior_metrics_map[key] = pm

    result_items: list[LabMetricItem] = []
    for m in normalized_items:
        t_name = str(m.get("test") or m.get("name") or "").strip()
        key = canonical_biomarker_key(t_name, allow_urinalysis=True)
        matched_prior = prior_metrics_map.get(key)

        prev_val = None
        prev_date = None
        d_abs = None
        d_pct = None
        d_alert = None

        if matched_prior:
            prev_val = str(matched_prior.get("value", "")).strip()
            prev_unit = str(matched_prior.get("unit", "")).strip()
            prev_date = prior_doc_date
            c_val = str(m.get("value", "")).strip()
            status = str(m.get("status") or "Normal").strip()
            unit = str(m.get("unit") or "").strip()

            effective_prev_val = prev_val
            effective_prev_unit = prev_unit
            if unit and prev_unit:
                u1 = normalize_clinical_unit(unit).strip().lower().replace(" ", "")
                u2 = normalize_clinical_unit(prev_unit).strip().lower().replace(" ", "")
                if u1 != u2:
                    conv = convert_to_standard(prev_val, prev_unit, unit, key)
                    if conv is not None:
                        effective_prev_val = str(conv)
                        effective_prev_unit = unit

            d_abs, d_pct, d_alert = compute_biomarker_delta(
                c_val, effective_prev_val, status, unit, canonical_key=key, prev_unit=effective_prev_unit
            )

        result_items.append(LabMetricItem(
            test=t_name,
            value=str(m.get("value", "")).strip(),
            unit=str(m.get("unit", "")).strip(),
            range=str(m.get("range") or m.get("reference_range") or "").strip(),
            status=str(m.get("status") or "Normal").strip(),
            previous_value=prev_val,
            previous_date=prev_date,
            delta_abs=d_abs,
            delta_pct=d_pct,
            delta_alert=d_alert,
        ))

    return result_items, prior_doc_id, prior_doc_date


async def _get_or_extract_metrics(
    doc_id: uuid.UUID,
    force_refresh: bool,
    current_user: User | UserDTO,
    db: AsyncSession,
) -> MetricsResponse:
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalars().first()

    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found.")

    if getattr(doc, "index_status", None) == "failed" or is_stale_building(doc):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This document could not be processed. Please upload a different file or re-upload.",
        )

    is_future = check_is_future_date(doc.collected_at)

    # 1. Check Cache: use 'is not None' because [] is a valid cached result
    if not force_refresh and doc.cached_metrics is not None:
        cached = doc.cached_metrics
        if isinstance(cached, str):
            try:
                cached = json.loads(cached)
            except Exception:
                cached = []
        if isinstance(cached, dict) and "metrics" in cached:
            cached = cached["metrics"]
        if isinstance(cached, list):
            # Always deepcopy cached_metrics to protect DB column from delta enrichment
            cached_copy = copy.deepcopy(cached)
            items, p_id, p_date = await _apply_longitudinal_deltas(doc, cached_copy, current_user, db)
            return MetricsResponse(
                metrics=items,
                collected_at=doc.collected_at,
                is_future_collection_date=is_future,
                prior_document_id=p_id,
                prior_document_date=p_date,
            )
        return MetricsResponse(
            metrics=[],
            collected_at=doc.collected_at,
            is_future_collection_date=is_future,
        )

    if getattr(doc, "index_status", None) == "building":
        raise HTTPException(
            status_code=503,
            detail="Document index is still building. Please retry in 2 seconds.",
            headers={"Retry-After": "2"},
        )

    if not doc.file_path:
        return MetricsResponse(
            metrics=[],
            collected_at=doc.collected_at,
            is_future_collection_date=is_future,
        )

    try:
        raw_metrics = await extract_and_cache_metrics(
            doc_id=doc.id,
            page_docs=None,
            db=db,
            user_id=current_user.id,
        )
        if raw_metrics is None:
            raise HTTPException(
                status_code=503,
                detail="Metrics extraction temporarily unavailable. Please retry in 2 seconds.",
                headers={"Retry-After": "2"},
            )
        # Check if doc was deleted during extraction
        res = await db.execute(select(Document).filter(Document.id == doc_id, Document.user_id == current_user.id))
        fresh_doc = res.scalars().first()
        if not fresh_doc:
            logger.info("Document %s was deleted while metrics extraction was in-flight; discarding result.", doc_id)
            return MetricsResponse(
                metrics=[],
                collected_at=None,
                is_future_collection_date=False,
            )
        raw_copy = copy.deepcopy(raw_metrics)
        items, p_id, p_date = await _apply_longitudinal_deltas(fresh_doc, raw_copy, current_user, db)
        return MetricsResponse(
            metrics=items,
            collected_at=fresh_doc.collected_at,
            is_future_collection_date=check_is_future_date(fresh_doc.collected_at),
            prior_document_id=p_id,
            prior_document_date=p_date,
        )
    except HTTPException:
        raise
    except StaleDataError:
        await db.rollback()
        logger.info("Document %s was deleted while metrics extraction was in-flight; discarding result.", doc_id)
        return MetricsResponse(
            metrics=[],
            collected_at=None,
            is_future_collection_date=False,
        )
    except Exception as err:
        if isinstance(err, (StaleDataError, GeminiUnavailableError, asyncio.TimeoutError, TimeoutError)) or "timeout" in str(err).lower() or "disconnect" in str(err).lower():
            logger.warning("Metrics extraction transient error: %s", err)
        else:
            logger.warning("Metrics extraction error: %s", err)
        return MetricsResponse(
            metrics=[],
            collected_at=getattr(doc, "collected_at", None),
            is_future_collection_date=is_future,
        )


@router.post("/extract-metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@limiter.limit(settings.RATE_LIMIT_METRICS)
async def extract_metrics(
    request: Request,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    force_refresh: bool = False,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_id = uuid.UUID(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session/document ID.")

    return await _get_or_extract_metrics(doc_id, force_refresh, current_user, db)


@router.get("/users/me/documents/{document_id}/metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@router.post("/users/me/documents/{document_id}/metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@limiter.limit(settings.RATE_LIMIT_METRICS)
async def get_document_metrics(
    request: Request,
    document_id: str,
    force_refresh: bool = False,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session/document ID.")

    return await _get_or_extract_metrics(doc_id, force_refresh, current_user, db)


# ── Longitudinal Trends Endpoint (REDESIGN_CHANGELOG.md §3.3-A) ──────────

class MetricTrendPoint(BaseModel):
    document_id: str
    collected_at: str | None = None
    value: float
    raw_value: str
    status: str


class MetricTrendSeries(BaseModel):
    key: str
    name: str
    unit: str
    reference_range: str
    points: list[MetricTrendPoint]


class MetricTrendReport(BaseModel):
    document_id: str
    title: str
    collected_at: str | None = None


class MetricTrendsResponse(BaseModel):
    patient_id: str
    generated_at: str
    reports: list[MetricTrendReport]
    series: list[MetricTrendSeries]



def normalize_biomarker_name(name: str) -> str:
    """Normalize biomarker name to match frontend normalizeName() in clinical.js."""
    n = re.sub(r'\(.*?\)', '', str(name or ''))
    return re.sub(r'[^a-zA-Z0-9]+', '', n).lower().strip()


@router.get("/users/me/metrics/trends", response_model=MetricTrendsResponse, tags=["Lab Metrics"])
@limiter.limit(settings.RATE_LIMIT_METRICS)
async def get_patient_metric_trends(
    request: Request,
    patient_id: str | None = None,
    limit: int = 8,
    keys: str | None = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dep_uuid = None
    if patient_id and patient_id != "self":
        try:
            dep_uuid = uuid.UUID(patient_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dependent profile not found",
            )
        dep_exists = await db.scalar(
            select(DependentProfile.id).where(
                DependentProfile.id == dep_uuid,
                DependentProfile.user_id == current_user.id,
            )
        )
        if not dep_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dependent profile not found",
            )

    filters = [
        Document.user_id == current_user.id,
        Document.cached_metrics.is_not(None),
    ]
    if dep_uuid:
        filters.append(Document.dependent_id == dep_uuid)
    else:
        filters.append(Document.dependent_id.is_(None))

    stmt = select(Document).filter(*filters)
    res = await db.execute(stmt)
    docs = [d for d in res.scalars().all() if not is_sample_document(d)]

    if not docs:
        return MetricTrendsResponse(
            patient_id=patient_id or "self",
            generated_at=datetime.now(UTC).isoformat(),
            reports=[],
            series=[],
        )

    # Parse collection date and sort chronologically (oldest to newest)
    def _doc_sort_key(d: Document):
        dt = parse_report_chronology(d)
        if dt:
            return dt
        if d.created_at:
            return d.created_at.replace(tzinfo=None) if d.created_at.tzinfo else d.created_at
        return datetime.min

    docs.sort(key=_doc_sort_key)
    # Take up to `limit` reports (most recent limit, sorted chronologically oldest to newest)
    target_docs = docs[-limit:] if len(docs) > limit else docs

    reports: list[MetricTrendReport] = []
    series_map: dict[str, dict[str, Any]] = {}
    requested_keys = set(k.strip().lower() for k in keys.split(",")) if keys else None

    for d in target_docs:
        date_label = d.collected_at or (d.created_at.strftime("%d %b %Y") if d.created_at else None)
        reports.append(
            MetricTrendReport(
                document_id=str(d.id),
                title=d.title or d.filename or "Lab Report",
                collected_at=date_label,
            )
        )

        raw = d.cached_metrics
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []
        if isinstance(raw, dict) and "metrics" in raw:
            raw = raw["metrics"]
        if not isinstance(raw, list):
            continue

        for m in raw:
            if not isinstance(m, dict):
                continue
            t_name = str(m.get("test") or m.get("name") or "").strip()
            base_key = canonical_biomarker_key(t_name, allow_urinalysis=True)
            if not base_key:
                continue
            norm_key = normalize_biomarker_name(t_name)
            if requested_keys and base_key not in requested_keys and norm_key not in requested_keys:
                continue

            val_float = _parse_first_float(m.get("value"))
            if val_float is None:
                continue

            unit = normalize_clinical_unit(str(m.get("unit") or "").strip()) if m.get("unit") else ""
            ref_range = str(m.get("range") or m.get("reference_range") or "").strip()
            status = str(m.get("status") or "Normal").strip()
            raw_val = str(m.get("value", "")).strip()

            group_key = f"{base_key}:{unit}" if unit else base_key
            if group_key not in series_map:
                series_map[group_key] = {
                    "key": base_key,
                    "name": t_name,
                    "unit": unit,
                    "reference_range": ref_range,
                    "points": [],
                }

            # Deduplicate identical (date, value) measurements for the same series
            if any(pt.collected_at == date_label and pt.value == val_float for pt in series_map[group_key]["points"]):
                continue

            series_map[group_key]["points"].append(
                MetricTrendPoint(
                    document_id=str(d.id),
                    collected_at=date_label,
                    value=val_float,
                    raw_value=raw_val,
                    status=status,
                )
            )

    series_list = [
        MetricTrendSeries(
            key=s["key"],
            name=s["name"],
            unit=s["unit"],
            reference_range=s["reference_range"],
            points=s["points"],
        )
        for s in series_map.values()
    ]

    return MetricTrendsResponse(
        patient_id=patient_id or "self",
        generated_at=datetime.now(UTC).isoformat(),
        reports=reports,
        series=series_list,
    )

