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

    extract_prompt = f"""
    Extract structured medical lab values from the following report text into a clean JSON array.
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
        from app.llm.gemini_client import call_gemini_with_retry
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
        metrics = [LabMetricItem(**item) for item in parsed]
        return MetricsResponse(metrics=metrics)
    except Exception as err:
        logger.error("Metrics extraction error: %s", err)
        return MetricsResponse(metrics=[])
