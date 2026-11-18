from datetime import date, datetime
from uuid import UUID

from app.core.security import sanitize_text
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Password must be 8-72 characters (bcrypt limit)."
    )
    phi_consent_granted: bool

class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=120)
    date_of_birth: date | None = None
    biological_sex: str | None = None
    blood_type: str | None = None
    pre_existing_conditions: str | None = Field(None, max_length=2000)
    known_allergies: str | None = Field(None, max_length=1000)
    current_medications: str | None = Field(None, max_length=2000)
    language_preference: str | None = None
    emergency_contact_name: str | None = Field(None, max_length=120)
    emergency_contact_phone: str | None = Field(None, max_length=32)
    height_cm: float | None = None
    weight_kg: float | None = None
    diet_type: str | None = None
    activity_level: str | None = None
    occupation: str | None = Field(None, max_length=120)
    memory_consent_granted: bool | None = None

    @field_validator("height_cm")
    @classmethod
    def validate_height_cm(cls, v: float | None) -> float | None:
        if v is not None:
            if v < 30.0 or v > 280.0:
                raise ValueError("height_cm must be between 30 and 280 cm")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight_kg(cls, v: float | None) -> float | None:
        if v is not None:
            if v < 2.0 or v > 400.0:
                raise ValueError("weight_kg must be between 2 and 400 kg")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: date | None) -> date | None:
        if v is not None:
            if v < date(1900, 1, 1) or v > date.today():
                raise ValueError("date_of_birth must be between 1900-01-01 and today.")
        return v

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: str | None) -> str | None:
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
    def sanitize_user_strings(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime
    
    full_name: str | None = None
    date_of_birth: date | None = None
    calculated_age: int | None = None
    biological_sex: str | None = None
    blood_type: str | None = None
    pre_existing_conditions: str | None = None
    known_allergies: str | None = None
    current_medications: str | None = None
    language_preference: str | None = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    bmi_info: dict | None = None
    diet_type: str | None = None
    activity_level: str | None = None
    occupation: str | None = None
    memory_consent_granted: bool = False

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class MemoryConsentRequest(BaseModel):
    consent: bool
    clear_existing: bool | None = False


class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New chat session title")


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class PatientFactCreate(BaseModel):
    fact_type: str = Field(..., description="condition|medication|allergy|family_history|symptom|lifestyle|measurement|procedure|weight|sport_hobby")
    fact_text: str = Field(..., max_length=500)
    confidence: float | None = Field(1.0, ge=0.0, le=1.0)
    source_type: str | None = "user_edit"
    source_excerpt: str | None = None
    dependent_id: UUID | None = None
    patient_id: str | None = None

    @field_validator("fact_text", mode="before")
    @classmethod
    def sanitize_fact_text(cls, v: str) -> str:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class PatientFactUpdate(BaseModel):
    fact_type: str | None = None
    fact_text: str | None = Field(None, max_length=500)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    is_active: bool | None = None
    is_user_verified: bool | None = None

    @field_validator("fact_text", mode="before")
    @classmethod
    def sanitize_fact_text_update(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v


class PatientFactResponse(BaseModel):
    id: UUID
    user_id: UUID
    dependent_id: UUID | None = None
    fact_type: str
    fact_text: str
    confidence: float = 1.0
    is_active: bool = True
    is_user_verified: bool = False
    source_type: str = "chat"
    source_id: str | None = None
    source_excerpt: str | None = None
    source_document_id: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_path: str | None = None
    title: str | None = None
    collected_at: str | None = None
    is_future_collection_date: bool | None = False
    created_at: str | None = None
    dependent_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RenameDocumentRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=60, description="New document title (max 60 chars)")


class ReassignDocumentPatientRequest(BaseModel):
    patient_id: str = Field(..., description="'self' or dependent UUID string")


class CustomVerificationRequest(BaseModel):
    email: EmailStr

