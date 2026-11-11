from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime, date
from app.core.security import sanitize_text

class DependentBase(BaseModel):
    relationship: str
    full_name: str
    date_of_birth: Optional[date] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    pre_existing_conditions: Optional[str] = None
    known_allergies: Optional[str] = None
    current_medications: Optional[str] = None
    height_cm: Optional[float] = None
    diet_type: Optional[str] = None
    activity_level: Optional[str] = None
    occupation: Optional[str] = None

    @field_validator("height_cm")
    @classmethod
    def validate_height_cm(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v < 30.0 or v > 280.0:
                raise ValueError("height_cm must be between 30 and 280 cm")
        return v

    @field_validator(
        "relationship",
        "full_name",
        "occupation",
        "pre_existing_conditions",
        "known_allergies",
        "current_medications",
        mode="before",
    )
    @classmethod
    def sanitize_dependent_strings(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class DependentCreate(DependentBase):
    pass

class DependentUpdate(BaseModel):
    relationship: Optional[str] = None
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    pre_existing_conditions: Optional[str] = None
    known_allergies: Optional[str] = None
    current_medications: Optional[str] = None
    height_cm: Optional[float] = None
    diet_type: Optional[str] = None
    activity_level: Optional[str] = None
    occupation: Optional[str] = None

    @field_validator("height_cm")
    @classmethod
    def validate_height_cm(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if v < 30.0 or v > 280.0:
                raise ValueError("height_cm must be between 30 and 280 cm")
        return v

    @field_validator(
        "relationship",
        "full_name",
        "occupation",
        "pre_existing_conditions",
        "known_allergies",
        "current_medications",
        mode="before",
    )
    @classmethod
    def sanitize_dependent_update_strings(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class DependentResponse(DependentBase):
    id: UUID
    user_id: UUID
    calculated_age: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
