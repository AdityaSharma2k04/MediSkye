from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime, date

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,
        description="Password must be 8-72 characters (bcrypt limit)."
    )
    phi_consent_granted: bool

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = None
    pre_existing_conditions: Optional[str] = None
    known_allergies: Optional[str] = None
    current_medications: Optional[str] = None
    language_preference: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

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

    class Config:
        from_attributes = True



class Token(BaseModel):
    access_token: str
    token_type: str
