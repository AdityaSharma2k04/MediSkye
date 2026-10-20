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

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/extract-metrics", response_model=MetricsResponse, tags=["Lab Metrics"])
@limiter.limit("10/minute")
async def extract_metrics(
    request: Request,
    x_session_id: str = Header(..., alias="X-Session-ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        doc_id = uuid.UUID(x_session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session/document ID.")
        
    result = await db.execute(select(Document).filter(Document.id == doc_id, Document.user_id == current_user.id))
    doc = result.scalars().first()

    if not doc or not doc.file_path:
        return MetricsResponse(metrics=[])

    try:
        vectorstore = await asyncio.to_thread(
            FAISS.load_local, doc.file_path, get_embedder(), allow_dangerous_deserialization=True
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Could not load document index.")

    docs = await asyncio.to_thread(
        retrieve_relevant_docs, "blood count lab results reference ranges cholesterol liver function", vectorstore, k=6
    )
    combined_text = "\n".join([d.page_content for d in docs])

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

    try:
        response = await call_gemini_with_retry(
            contents=extract_prompt,
            user_id=current_user.id,
            backoff_delays=[1.5, 4.0, 16.0],
        )
        if not response or not response.text:
            return MetricsResponse(metrics=[])
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3].strip()
        elif text.startswith("```"):
            text = text[3:-3].strip()
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return MetricsResponse(metrics=[])

        ignored_keywords = (
            "iso 15189", "iso", "nabl", "cap", "certified", "central facility", "facility",
            "hospital", "laboratory", "lab", "helpline", "boulevard", "street",
            "report id", "accession", "sample", "patient name", "referred by", "page", "phone"
        )

        metrics = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            test_name = str(item.get("test") or item.get("name") or "").strip()
            val_str = str(item.get("value", "")).strip()
            unit_str = str(item.get("unit", "")).strip()

            test_lower = test_name.lower()
            val_lower = val_str.lower()

            # Ignore entries matching banned header/footer keywords case-insensitively
            if any(kw in test_lower or kw in val_lower for kw in ignored_keywords):
                continue

            # Require valid biomarker name, value, and non-empty unit
            if not test_name or not val_str or not unit_str:
                continue

            metric_dict = {
                "test": test_name,
                "value": val_str,
                "unit": unit_str,
                "range": str(item.get("range") or item.get("reference_range") or "").strip(),
                "status": str(item.get("status") or "Normal").strip(),
            }
            metrics.append(LabMetricItem(**metric_dict))

        return MetricsResponse(metrics=metrics)
    except Exception as err:
        logger.error("Metrics extraction error: %s", err)
        return MetricsResponse(metrics=[])
