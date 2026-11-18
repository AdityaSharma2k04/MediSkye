from datetime import date, datetime
from uuid import UUID

from app.core.security import sanitize_text
from pydantic import BaseModel, ConfigDict, field_validator


class DependentBase(BaseModel):
    relationship: str
    full_name: str
    date_of_birth: date | None = None
    biological_sex: str | None = None
    blood_type: str | None = None
    pre_existing_conditions: str | None = None
    known_allergies: str | None = None
    current_medications: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    diet_type: str | None = None
    activity_level: str | None = None
    occupation: str | None = None

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
    def sanitize_dependent_strings(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class DependentCreate(DependentBase):
    pass

class DependentUpdate(BaseModel):
    relationship: str | None = None
    full_name: str | None = None
    date_of_birth: date | None = None
    biological_sex: str | None = None
    blood_type: str | None = None
    pre_existing_conditions: str | None = None
    known_allergies: str | None = None
    current_medications: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    diet_type: str | None = None
    activity_level: str | None = None
    occupation: str | None = None

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
    def sanitize_dependent_update_strings(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return sanitize_text(v)
        return v

class DependentResponse(DependentBase):
    id: UUID
    user_id: UUID
    calculated_age: int | None = None
    bmi_info: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
