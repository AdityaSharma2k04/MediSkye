from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
from app.core.security import sanitize_text


class QueryRequest(BaseModel):
    session_id: str = Field(..., description="UUID representation of user chat session")
    query: str = Field(..., min_length=1, max_length=2000, description="Medical query string")
    language: Optional[str] = Field("English", description="Target response language")
    patient_id: Optional[str] = Field(None, description="Optional patient/dependent ID")
    provider: Optional[str] = Field(None, description="Optional LLM provider: 'gemini' | 'agentrouter'")

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
