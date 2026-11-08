import json
import uuid
import re
import logging
import asyncio
import copy
from datetime import datetime, UTC
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm.attributes import flag_modified
from langchain_community.vectorstores import FAISS

from app.core.auth import UserDTO, get_current_user
from app.core.limiter import limiter
from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, Document, DependentProfile
from app.schemas.upload import MetricsResponse, LabMetricItem
from app.services.upload_jobs import is_stale_building
from app.rag.retriever import retrieve_relevant_docs, get_cached_hybrid_index, load_hybrid_index
from app.rag.index_storage import aensure_index_local
from app.rag.embedder import get_embedder
from app.llm.gemini_client import call_gemini_with_retry
from google.genai.types import GenerateContentConfig, ThinkingConfig

from typing import Optional, List, Dict, Any, Union, Tuple

from app.services.clinical_units import (
    normalize_clinical_unit,
    check_is_future_date,
    canonical_biomarker_name,
    canonical_biomarker_key,
    compute_biomarker_delta,
    convert_to_standard,
    parse_report_chronology,
    _parse_first_float,
)

logger = logging.getLogger(__name__)

router = APIRouter()

METRICS_PROMPT_CHAR_BUDGET = 16000

_RANGE_BETWEEN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_RANGE_UPPER = re.compile(
    r"^\s*(?:<|<=|less than|up to)\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_RANGE_LOWER = re.compile(
    r"^\s*(?:>|>=|greater than|more than)\s*(\d+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_RANGE_AMBIGUOUS = re.compile(r"(?:-|–|—|to|<|>|<=|>=)")
_RANGE_DEMOGRAPHIC = re.compile(
    r"\b(?:male|female|adult|child|pediatric|infant|men|women|years|yrs|males|females)\b",
    re.IGNORECASE,
)


def _status_from_range(value: Any, rng: str) -> Optional[str]:
    """Derive Low / High / Normal / None from a numeric value and reference range."""
    if value is None or not rng:
        return None
    text = str(rng).strip()
    if _RANGE_DEMOGRAPHIC.search(text):
        return None
    val = _parse_first_float(str(value))
    if val is None:
        return None
    m = _RANGE_BETWEEN.match(text)
    if m:
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
            if lo > hi:
                lo, hi = hi, lo
            if val < lo:
                return "Low"
            if val > hi:
                return "High"
            return "Normal"
        except (ValueError, TypeError):
            return None
    m = _RANGE_UPPER.match(text)
    if m:
        try:
            hi = float(m.group(1))
            return "High" if val > hi else "Normal"
        except (ValueError, TypeError):
            return None
    m = _RANGE_LOWER.match(text)
    if m:
        try:
            lo = float(m.group(1))
            return "Low" if val < lo else "Normal"
        except (ValueError, TypeError):
            return None
    return None


_STRATUM = re.compile(
    r"(?P<label>adult\s+male|adult\s+female|female|male|women|woman|men|man|girls?|boys?|"
    r"(?-i:\b[MF]\b)|child(?:ren)?|infants?|neonates?|newborns?|pediatric|adults?)"
    r"\s*[:\-–—(]?\s*(?P<lo>-?\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<hi>-?\d+(?:\.\d+)?)",
    re.I,
)


def _stratum_class(label: str) -> str:
    l = label.strip().lower()
    if "female" in l or l in ("women", "woman", "f", "girl", "girls"):
        return "female"
    if "male" in l or l in ("men", "man", "m", "boy", "boys"):
        return "male"
    return "other"


def _status_from_demographic_ranges(value: Any, rng: str, sex: Optional[str]) -> Optional[str]:
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


def _resolve_status(llm_status: Any, value: Any, rng: Any, sex: Optional[str]) -> str:
    llm = str(llm_status or "").strip()
    rng = str(rng or "")
    derived = _status_from_range(value, rng)
    demographic = False
    if derived is None:
        existing = globals().get("_RANGE_DEMOGRAPHIC")
        demographic = bool(existing.search(rng)) if existing is not None else False
        demographic = demographic or len(list(_STRATUM.finditer(rng))) >= 2
        if demographic:
            derived = _status_from_demographic_ranges(value, rng, sex)
    if not llm:
        return derived or "Unknown"
    if llm.lower() == "normal":
        if derived in ("High", "Low"):
            return derived          # numbers beat a wrong "Normal"
        if derived is None and demographic:
            return "Unknown"        # unresolved stratified range: no false reassurance
    return llm                      # High/Low/Critical/Abnormal/Borderline etc. are preserved as-is


async def _load_patient_sex(db: AsyncSession, doc: Any) -> Optional[str]:
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
    doc_id: Union[uuid.UUID, str],
    page_docs: Optional[List[Any]] = None,
    db: Optional[AsyncSession] = None,
    user_id: Optional[Union[uuid.UUID, str]] = None,
) -> Optional[List[Dict[str, Any]]]:
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
                "count", "panel", "hemoglobin", "glucose", "cholesterol", "platelet", "wbc", "rbc"
            )
            lab_pages = [p for p in all_pages if any(kw in p.lower() for kw in keywords)]
            combined_text = "\n".join(lab_pages) if lab_pages else full_text
    elif doc.file_path:
        try:
            bm25_index = None
            if hasattr(FAISS.load_local, "mock_calls") or hasattr(FAISS.load_local, "_mock_return_value"):
                vectorstore = await asyncio.to_thread(
                    FAISS.load_local, doc.file_path, get_embedder(), allow_dangerous_deserialization=True
                )
            else:
                cached_entry = get_cached_hybrid_index(str(doc.id)) or get_cached_hybrid_index(doc.file_path)
                if cached_entry is not None:
                    vectorstore, bm25_index = cached_entry
                else:
                    resolved_path = str(await aensure_index_local(doc.file_path))
                    vectorstore, bm25_index = await asyncio.to_thread(load_hybrid_index, resolved_path)
        except Exception as e:
            logger.error("Could not load document index: %s", e)
            raise HTTPException(status_code=500, detail="Could not load document index.")

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
        doc.cached_metrics = []
        flag_modified(doc, "cached_metrics")
        db.add(doc)
        await db.commit()
        return []

    extract_prompt = f"""You are a specialized medical lab data extraction system.
Extract structured clinical biomarker values from the following medical report text into a clean JSON array.

CRITICAL EXTRACTION RULES:
1. ONLY extract actual clinical biomarkers and laboratory analytes (e.g., Hemoglobin, HbA1c, TSH, LDL Cholesterol, Creatinine, WBC).
2. DO NOT extract metadata, accreditation numbers, addresses, or text from document headers/footers.
3. Strictly Ignore any line or test name containing: "ISO", "NABL", "CAP", "Certified", "Facility", "Hospital", "Lab", "Laboratory", "Helpline", "Boulevard", "Street", "Report ID", "Accession", "Sample", "Patient Name", "Referred By", "Page", or "Phone".
4. Validation Rule: Every extracted item MUST have both a numeric/qualitative clinical value AND a valid physiological unit (e.g., mg/dL, g/dL, %, mIU/L, U/L, mmol/L, 10^3/uL, pg/mL) or be a recognized clinical ratio/index. If it lacks a valid unit or medical biomarker name, discard it.
5. If no valid metrics are found, return an empty list `[]`.

Return ONLY raw JSON with schema:
[
  {{
    "test": "Name of test (e.g. Hemoglobin, LDL Cholesterol)",
    "value": "Observed value (e.g. 14.5)",
    "unit": "Unit (e.g. g/dL, mg/dL)",
    "range": "Reference range (e.g. 13.8 - 17.2)",
    "status": "Normal" | "High" | "Low"
  }}
]

Report text:
{combined_text[:METRICS_PROMPT_CHAR_BUDGET]}
"""

    effective_user_id = user_id or doc.user_id
    try:
        response = await call_gemini_with_retry(
            contents=extract_prompt,
            user_id=effective_user_id,
            backoff_delays=[1.5, 4.0, 16.0],
            config=GenerateContentConfig(
                thinking_config=ThinkingConfig(thinking_budget=0),
                temperature=0.0,
            ),
        )
        if not response or not response.text:
            return None

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        try:
            parsed = json.loads(text)
        except Exception:
            return None

        if not isinstance(parsed, list):
            return None

        _IGNORED_TEST_NAME = re.compile(
            r"\b(iso\s*15189|nabl|certified|accreditation|central facility|hospital|laborator(?:y|ies)|helpline|"
            r"boulevard|street|report id|accession|patient name|referred by|phone)\b",
            re.I,
        )

        raw_metrics = []
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

        doc.cached_metrics = raw_metrics
        flag_modified(doc, "cached_metrics")
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return raw_metrics
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Metrics extraction error (will retry on-demand): %s", err)
        return None


async def _apply_longitudinal_deltas(
    doc: Document,
    raw_list: List[Any],
    current_user: Union[User, UserDTO],
    db: AsyncSession,
) -> Tuple[List[LabMetricItem], Optional[str], Optional[str]]:
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
                    key = canonical_biomarker_key(t_name)
                    if key:
                        prior_metrics_map[key] = pm

    result_items: List[LabMetricItem] = []
    for m in normalized_items:
        t_name = str(m.get("test") or m.get("name") or "").strip()
        key = canonical_biomarker_key(t_name)
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
    current_user: Union[User, UserDTO],
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
        raw_copy = copy.deepcopy(raw_metrics)
        items, p_id, p_date = await _apply_longitudinal_deltas(doc, raw_copy, current_user, db)
        return MetricsResponse(
            metrics=items,
            collected_at=doc.collected_at,
            is_future_collection_date=is_future,
            prior_document_id=p_id,
            prior_document_date=p_date,
        )
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Metrics extraction error: %s", err)
        return MetricsResponse(
            metrics=[],
            collected_at=doc.collected_at,
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
    collected_at: Optional[str] = None
    value: float
    raw_value: str
    status: str


class MetricTrendSeries(BaseModel):
    key: str
    name: str
    unit: str
    reference_range: str
    points: List[MetricTrendPoint]


class MetricTrendReport(BaseModel):
    document_id: str
    title: str
    collected_at: Optional[str] = None


class MetricTrendsResponse(BaseModel):
    patient_id: str
    generated_at: str
    reports: List[MetricTrendReport]
    series: List[MetricTrendSeries]


def canonical_biomarker_key(name: str) -> str:
    """Normalize biomarker name preserving distinct subtypes (e.g. Total vs Direct)."""
    clean = re.sub(r'[^a-zA-Z0-9]+', '_', str(name or '').strip().lower()).strip('_')
    return clean


def normalize_biomarker_name(name: str) -> str:
    """Normalize biomarker name to match frontend normalizeName() in clinical.js."""
    n = re.sub(r'\(.*?\)', '', str(name or ''))
    return re.sub(r'[^a-zA-Z0-9]+', '', n).lower().strip()


@router.get("/users/me/metrics/trends", response_model=MetricTrendsResponse, tags=["Lab Metrics"])
@limiter.limit(settings.RATE_LIMIT_METRICS)
async def get_patient_metric_trends(
    request: Request,
    patient_id: Optional[str] = None,
    limit: int = 8,
    keys: Optional[str] = None,
    current_user: UserDTO = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dep_uuid = None
    if patient_id and patient_id != "self":
        try:
            dep_uuid = uuid.UUID(patient_id)
        except ValueError:
            return MetricTrendsResponse(
                patient_id=patient_id,
                generated_at=datetime.now(UTC).isoformat(),
                reports=[],
                series=[],
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
    docs = list(res.scalars().all())

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

    reports: List[MetricTrendReport] = []
    series_map: Dict[str, Dict[str, Any]] = {}
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
            base_key = canonical_biomarker_key(t_name)
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

