import json
import uuid
import logging
import asyncio
from fastapi import APIRouter, Depends, Header, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from langchain_community.vectorstores import FAISS

from app.core.config import settings
from app.core.auth import get_current_user
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import User, Document
from app.schemas.upload import MetricsResponse, LabMetricItem
from app.rag.retriever import retrieve_relevant_docs
from app.rag.embedder import get_embedder
from app.llm.gemini_client import call_gemini_with_retry

from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger(__name__)

router = APIRouter()


async def extract_and_cache_metrics(
    doc_id: Union[uuid.UUID, str],
    page_docs: Optional[List[Any]] = None,
    db: Optional[AsyncSession] = None,
    user_id: Optional[Union[uuid.UUID, str]] = None,
) -> List[Dict[str, Any]]:
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

    combined_text = ""
    if page_docs:
        all_pages = [getattr(d, "page_content", str(d)) for d in page_docs if getattr(d, "page_content", str(d))]
        full_text = "\n".join(all_pages)
        if len(full_text) <= 4000:
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
            vectorstore = await asyncio.to_thread(
                FAISS.load_local, doc.file_path, get_embedder(), allow_dangerous_deserialization=True
            )
        except Exception as e:
            logger.error("Could not load document index: %s", e)
            raise HTTPException(status_code=500, detail="Could not load document index.")

        docs = await asyncio.to_thread(
            retrieve_relevant_docs, "blood count lab results reference ranges cholesterol liver function", vectorstore, k=6
        )
        combined_text = "\n".join([d.page_content for d in docs])
    else:
        return []

    if not combined_text.strip():
        doc.cached_metrics = []
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
{combined_text[:4000]}
"""

    effective_user_id = user_id or doc.user_id
    try:
        response = await call_gemini_with_retry(
            contents=extract_prompt,
            user_id=effective_user_id,
            backoff_delays=[1.5, 4.0, 16.0],
        )
        if not response or not response.text:
            doc.cached_metrics = []
            db.add(doc)
            await db.commit()
            return []

        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            doc.cached_metrics = []
            db.add(doc)
            await db.commit()
            return []

        ignored_keywords = (
            "iso 15189", "iso", "nabl", "cap", "certified", "central facility", "facility",
            "hospital", "laboratory", "lab", "helpline", "boulevard", "street",
            "report id", "accession", "sample", "patient name", "referred by", "page", "phone"
        )

        raw_metrics = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            test_name = str(item.get("test") or item.get("name") or "").strip()
            val_str = str(item.get("value", "")).strip()
            unit_str = str(item.get("unit", "")).strip()

            test_lower = test_name.lower()
            val_lower = val_str.lower()

            if any(kw in test_lower or kw in val_lower for kw in ignored_keywords):
                continue

            if not test_name or not val_str or not unit_str:
                continue

            metric_dict = {
                "test": test_name,
                "value": val_str,
                "unit": unit_str,
                "range": str(item.get("range") or item.get("reference_range") or "").strip(),
                "status": str(item.get("status") or "Normal").strip(),
            }
            raw_metrics.append(metric_dict)

        doc.cached_metrics = raw_metrics
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return raw_metrics
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Metrics extraction error: %s", err)
        return []


async def _get_or_extract_metrics(
    doc_id: uuid.UUID,
    force_refresh: bool,
    current_user: User,
    db: AsyncSession,
) -> MetricsResponse:
    result = await db.execute(select(Document).filter(Document.id == doc_id))
    doc = result.scalars().first()

    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found.")

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
            parsed_metrics = []
            for item in cached:
                if isinstance(item, dict):
                    parsed_metrics.append(LabMetricItem(**item))
                elif isinstance(item, LabMetricItem):
                    parsed_metrics.append(item)
            return MetricsResponse(metrics=parsed_metrics)
        return MetricsResponse(metrics=[])

    if not doc.file_path:
        return MetricsResponse(metrics=[])

    try:
        raw_metrics = await extract_and_cache_metrics(
            doc_id=doc.id,
            page_docs=None,
            db=db,
            user_id=current_user.id,
        )
        parsed_metrics = [
            LabMetricItem(**item) if isinstance(item, dict) else item
            for item in raw_metrics
        ]
        return MetricsResponse(metrics=parsed_metrics)
    except HTTPException:
        raise
    except Exception as err:
        logger.error("Metrics extraction error: %s", err)
        return MetricsResponse(metrics=[])


@router.post("/extract-metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@limiter.limit("10/minute")
async def extract_metrics(
    request: Request,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_id = uuid.UUID(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session/document ID.")

    return await _get_or_extract_metrics(doc_id, force_refresh, current_user, db)


@router.get("/users/me/documents/{document_id}/metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@router.post("/users/me/documents/{document_id}/metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@limiter.limit("10/minute")
async def get_document_metrics(
    request: Request,
    document_id: str,
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session/document ID.")

    return await _get_or_extract_metrics(doc_id, force_refresh, current_user, db)

