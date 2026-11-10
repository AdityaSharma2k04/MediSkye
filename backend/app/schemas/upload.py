from typing import Optional, List
from pydantic import BaseModel



class UploadJobResponse(BaseModel):
    job_id: str
    status_url: str


class UploadStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: Optional[str] = None
    index_status: Optional[str] = None
    document_id: Optional[str] = None
    error: Optional[str] = None


class LabMetricItem(BaseModel):
    test: str
    value: str
    unit: str
    range: str
    status: str
    previous_value: Optional[str] = None
    previous_date: Optional[str] = None
    delta_abs: Optional[str] = None
    delta_pct: Optional[str] = None
    delta_alert: Optional[str] = None


class MetricsResponse(BaseModel):
    metrics: List[LabMetricItem]
    collected_at: Optional[str] = None
    is_future_collection_date: Optional[bool] = False
    prior_document_id: Optional[str] = None
    prior_document_date: Optional[str] = None
