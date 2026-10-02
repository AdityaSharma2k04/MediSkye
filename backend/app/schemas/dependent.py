from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime, date

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

class DependentResponse(DependentBase):
    id: UUID
    user_id: UUID
    calculated_age: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

