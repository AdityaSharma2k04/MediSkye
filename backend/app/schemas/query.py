from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.core.security import sanitize_text


class QueryRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="UUID representation of user chat session")
    document_id: Optional[str] = Field(None, description="Optional document ID if querying a specific document")
    document_ids: Optional[List[str]] = Field(None, description="Optional list of document IDs for multi-doc queries")
    query: str = Field(..., min_length=1, max_length=2000, description="Medical query string")
    language: Optional[str] = Field("English", description="Target response language")
    patient_id: Optional[str] = Field(None, description="Optional patient/dependent ID")


    @field_validator("query")
    def sanitize_query_text(cls, v: str) -> str:
        sanitized = sanitize_text(v)
        if not sanitized:
            raise ValueError("Query string cannot be blank or contain only control characters.")
        return sanitized


class SourceChunk(BaseModel):
    title: str
    page: int
    score: str
    excerpt: str


class QueryResponse(BaseModel):
    response: Optional[str] = None
    error: Optional[str] = None
    sources: Optional[List[SourceChunk]] = None
