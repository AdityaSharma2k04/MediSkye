from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from app.core.security import sanitize_text

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Password must be 8-72 characters (bcrypt limit)."
    )
    phi_consent_granted: bool

class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=120)
    date_of_birth: Optional[date] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    pre_existing_conditions: Optional[str] = Field(None, max_length=2000)
    known_allergies: Optional[str] = Field(None, max_length=1000)
    current_medications: Optional[str] = Field(None, max_length=2000)
    language_preference: Optional[str] = None
    emergency_contact_name: Optional[str] = Field(None, max_length=120)
    emergency_contact_phone: Optional[str] = Field(None, max_length=32)
    height_cm: Optional[float] = Field(None, ge=30.0, le=272.0)
    diet_type: Optional[str] = None
    activity_level: Optional[str] = None
    occupation: Optional[str] = Field(None, max_length=120)
    memory_consent_granted: Optional[bool] = None

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            if v < date(1900, 1, 1) or v > date.today():
                raise ValueError("date_of_birth must be between 1900-01-01 and today.")
        return v

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            from app.core.security import safe_language
            return safe_language(v)
        return v

    @field_validator(
        "full_name",
        "occupation",
        "emergency_contact_name",
        "pre_existing_conditions",
        "known_allergies",
        "current_medications",
        mode="before",
    )
    @classmethod
    def sanitize_user_strings(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime
    
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    calculated_age: Optional[int] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    pre_existing_conditions: Optional[str] = None
    known_allergies: Optional[str] = None
    current_medications: Optional[str] = None
    language_preference: Optional[str] = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    height_cm: Optional[float] = None
    diet_type: Optional[str] = None
    activity_level: Optional[str] = None
    occupation: Optional[str] = None
    memory_consent_granted: bool = False

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class MemoryConsentRequest(BaseModel):
    consent: bool
    clear_existing: Optional[bool] = False


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New chat session title")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class PatientFactCreate(BaseModel):
    fact_type: str = Field(..., description="condition|medication|allergy|family_history|symptom|lifestyle|measurement|procedure|weight|sport_hobby")
    fact_text: str = Field(..., max_length=500)
    confidence: Optional[float] = Field(1.0, ge=0.0, le=1.0)
    source_type: Optional[str] = "user_edit"
    source_excerpt: Optional[str] = None
    dependent_id: Optional[UUID] = None

    @field_validator("fact_text", mode="before")
    @classmethod
    def sanitize_fact_text(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class PatientFactUpdate(BaseModel):
    fact_type: Optional[str] = None
    fact_text: Optional[str] = Field(None, max_length=500)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    is_user_verified: Optional[bool] = None

    @field_validator("fact_text", mode="before")
    @classmethod
    def sanitize_fact_text_update(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class PatientFactResponse(BaseModel):
    id: UUID
    user_id: UUID
    dependent_id: Optional[UUID] = None
    fact_type: str
    fact_text: str
    confidence: float = 1.0
    is_active: bool = True
    is_user_verified: bool = False
    source_type: str = "chat"
    source_id: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_document_id: Optional[str] = None
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_path: Optional[str] = None
    title: Optional[str] = None
    collected_at: Optional[str] = None
    is_future_collection_date: Optional[bool] = False
    created_at: Optional[str] = None
    dependent_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RenameDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New document title (max 60 chars)")


class CustomVerificationRequest(BaseModel):
    email: EmailStr

