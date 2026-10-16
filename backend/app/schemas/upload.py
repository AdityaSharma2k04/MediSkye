from typing import Optional, List
from pydantic import BaseModel



class UploadResponse(BaseModel):
    message: str
    document_id: str


class UploadJobResponse(BaseModel):
    job_id: str
    status_url: str


class UploadStatusResponse(BaseModel):
    job_id: str
    status: str
    document_id: Optional[str] = None
    error: Optional[str] = None


class LabMetricItem(BaseModel):
    test: str
    value: str
    unit: str
    range: str
    status: str


class MetricsResponse(BaseModel):
    metrics: List[LabMetricItem]
