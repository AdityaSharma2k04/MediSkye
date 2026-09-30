import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Date, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as orm_relationship
from .database import Base
from .encryption import EncryptedString

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    full_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    biological_sex = Column(String, nullable=True)
    blood_type = Column(EncryptedString, nullable=True)
    pre_existing_conditions = Column(EncryptedString, nullable=True)
    known_allergies = Column(EncryptedString, nullable=True)
    emergency_contact_name = Column(String, nullable=True)
    emergency_contact_phone = Column(String, nullable=True)

    phi_consent_granted = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime, nullable=True)

    current_medications = Column(EncryptedString, nullable=True)
    language_preference = Column(String, default="English", nullable=True)

    documents = orm_relationship("Document", back_populates="owner")
    chats = orm_relationship("Chat", back_populates="user")
    audit_logs = orm_relationship("AuditLog", back_populates="user")
    dependents = orm_relationship("DependentProfile", back_populates="guardian", cascade="all, delete-orphan")


class DependentProfile(Base):
    __tablename__ = "dependent_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    relationship = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    biological_sex = Column(String, nullable=True)

    # PHI Columns (CRITICAL: MUST use EncryptedString)
    blood_type = Column(EncryptedString, nullable=True)
    pre_existing_conditions = Column(EncryptedString, nullable=True)
    known_allergies = Column(EncryptedString, nullable=True)
    current_medications = Column(EncryptedString, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    guardian = orm_relationship("User", back_populates="dependents")
    documents = orm_relationship("Document", back_populates="dependent")
    audit_logs = orm_relationship("AuditLog", back_populates="dependent")



class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)  # Path to FAISS index or PDF
    title = Column(String(60), nullable=True)  # User-defined or auto-generated chat title
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = orm_relationship("User", back_populates="documents")
    dependent = orm_relationship("DependentProfile", back_populates="documents")
    chats = orm_relationship("Chat", back_populates="document")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)  # Nullable: general-health chats have no document
    role = Column(String, nullable=False) # 'user' or 'ai'
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = orm_relationship("User", back_populates="chats")
    document = orm_relationship("Document", back_populates="chats")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String, nullable=False)
    resource = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = orm_relationship("User", back_populates="audit_logs")
    dependent = orm_relationship("DependentProfile", back_populates="audit_logs")


class Specialist(Base):
    __tablename__ = "specialists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    keywords = Column(JSON, nullable=False)
    contact_info = Column(String, nullable=True)

