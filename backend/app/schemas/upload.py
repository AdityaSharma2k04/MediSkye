from typing import Optional, List
from pydantic import BaseModel


class UploadResponse(BaseModel):
    message: str
    document_id: str


class LabMetricItem(BaseModel):
    test: str
    value: str
    unit: str
    range: str
    status: str


class MetricsResponse(BaseModel):
    metrics: List[LabMetricItem]
