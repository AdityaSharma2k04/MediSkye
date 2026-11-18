
from pydantic import BaseModel


class UploadJobResponse(BaseModel):
    job_id: str
    status_url: str


class UploadStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str | None = None
    index_status: str | None = None
    document_id: str | None = None
    error: str | None = None


class LabMetricItem(BaseModel):
    test: str
    value: str
    unit: str
    range: str
    status: str
    previous_value: str | None = None
    previous_date: str | None = None
    delta_abs: str | None = None
    delta_pct: str | None = None
    delta_alert: str | None = None


class MetricsResponse(BaseModel):
    metrics: list[LabMetricItem]
    collected_at: str | None = None
    is_future_collection_date: bool | None = False
    prior_document_id: str | None = None
    prior_document_date: str | None = None
