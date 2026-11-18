
from app.core.security import sanitize_text
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    session_id: str | None = Field(None, max_length=64, description="UUID representation of user chat session")
    document_id: str | None = Field(None, description="Optional document ID if querying a specific document")
    document_ids: list[str] | None = Field(None, max_length=10, description="Optional list of document IDs for multi-doc queries")
    query: str = Field(..., min_length=1, max_length=2000, description="Medical query string")
    language: str | None = Field("English", description="Target response language")
    patient_id: str | None = Field(None, description="Optional patient/dependent ID")


    @field_validator("query")
    def sanitize_query_text(cls, v: str) -> str:
        sanitized = sanitize_text(v)
        if not sanitized:
            raise ValueError("Query string cannot be blank or contain only control characters.")
        return sanitized
