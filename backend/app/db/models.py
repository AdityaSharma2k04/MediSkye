import uuid
from datetime import datetime, UTC
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Date,
    Boolean,
    JSON,
    Float,
    Integer,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as orm_relationship
from sqlalchemy.ext.hybrid import hybrid_property
from .database import Base
from .encryption import EncryptedString


def utcnow():
    """Timezone-aware UTC timestamp (replaces deprecated datetime.utcnow)."""
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    full_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    biological_sex = Column(String, nullable=True)
    blood_type = Column(EncryptedString, nullable=True)
    pre_existing_conditions = Column(EncryptedString, nullable=True)
    known_allergies = Column(EncryptedString, nullable=True)
    emergency_contact_name = Column(String, nullable=True)
    emergency_contact_phone = Column(String, nullable=True)

    phi_consent_granted = Column(Boolean, default=False)
    consent_timestamp = Column(DateTime(timezone=True), nullable=True)

    current_medications = Column(EncryptedString, nullable=True)
    language_preference = Column(String, default="English", nullable=True)

    # Extended Personalization Profile Fields (static)
    height_cm = Column(Float, nullable=True)
    diet_type = Column(String, nullable=True)       # vegetarian|non_vegetarian|vegan|eggetarian|jain|pescatarian|other
    activity_level = Column(String, nullable=True)  # sedentary|light|moderate|active|very_active
    occupation = Column(EncryptedString, nullable=True)

    # Patient Memory System — user must explicitly opt in
    memory_consent_granted = Column(Boolean, default=False, nullable=False)

    @property
    def health_profile(self):
        if getattr(self, "_phi_loaded", False):
            return {
                "blood_type": self.blood_type,
                "pre_existing_conditions": self.pre_existing_conditions,
                "known_allergies": self.known_allergies,
                "current_medications": self.current_medications,
                "height_cm": self.height_cm,
                "diet_type": self.diet_type,
                "activity_level": self.activity_level,
                "occupation": self.occupation,
            }
        from sqlalchemy.exc import InvalidRequestError
        raise InvalidRequestError("'User.health_profile' is set to lazy='raise', unable to load attribute for instance. Use get_current_user_full.")

    documents = orm_relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    chats = orm_relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    audit_logs = orm_relationship("AuditLog", back_populates="user")
    dependents = orm_relationship("DependentProfile", back_populates="guardian", cascade="all, delete-orphan")
    patient_facts = orm_relationship("PatientFact", back_populates="user", cascade="all, delete-orphan", foreign_keys="[PatientFact.user_id]")
    chat_chunks = orm_relationship("ChatChunk", back_populates="user", cascade="all, delete-orphan", foreign_keys="[ChatChunk.user_id]")
    upload_jobs = orm_relationship("UploadJob", back_populates="user", cascade="all, delete-orphan", foreign_keys="[UploadJob.user_id]")


class DependentProfile(Base):
    __tablename__ = "dependent_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    biological_sex = Column(String, nullable=True)

    # PHI Columns (CRITICAL: MUST use EncryptedString)
    blood_type = Column(EncryptedString, nullable=True)
    pre_existing_conditions = Column(EncryptedString, nullable=True)
    known_allergies = Column(EncryptedString, nullable=True)
    current_medications = Column(EncryptedString, nullable=True)

    # Extended Personalization Profile Fields (static)
    height_cm = Column(Float, nullable=True)
    diet_type = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)
    occupation = Column(EncryptedString, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    guardian = orm_relationship("User", back_populates="dependents")
    documents = orm_relationship("Document", back_populates="dependent")
    audit_logs = orm_relationship("AuditLog", back_populates="dependent")
    patient_facts = orm_relationship("PatientFact", back_populates="dependent", cascade="all, delete-orphan", foreign_keys="[PatientFact.dependent_id]")
    chat_chunks = orm_relationship("ChatChunk", back_populates="dependent", cascade="all, delete-orphan", foreign_keys="[ChatChunk.dependent_id]")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="SET NULL"), nullable=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)  # Path to FAISS index or PDF
    title = Column(String(60), nullable=True)  # User-defined or auto-generated chat title
    index_status = Column(String(20), default="local_ready", nullable=False)  # building | local_ready | synced
    cached_metrics = Column(JSON, nullable=True)
    cached_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    owner = orm_relationship("User", back_populates="documents")
    dependent = orm_relationship("DependentProfile", back_populates="documents")
    chats = orm_relationship("Chat", back_populates="document")
    chat_documents = orm_relationship("ChatDocument", back_populates="document", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True)  # Nullable: general-health chats have no document
    role = Column(String, nullable=False)  # 'user' or 'ai'
    message = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    user = orm_relationship("User", back_populates="chats")
    document = orm_relationship("Document", back_populates="chats")
    chat_chunks = orm_relationship("ChatChunk", back_populates="chat", cascade="all, delete-orphan")
    chat_documents = orm_relationship("ChatDocument", back_populates="chat", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String, nullable=False)
    resource = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    user = orm_relationship("User", back_populates="audit_logs")
    dependent = orm_relationship("DependentProfile", back_populates="audit_logs")


class PatientFact(Base):
    """
    PatientFact stores durable medical and personal facts extracted from conversations,
    documents, or user profile edits across chat sessions.
    """
    __tablename__ = "patient_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    fact_type = Column(String, nullable=False, index=True)  # condition|medication|allergy|family_history|symptom|lifestyle|measurement|procedure|weight|sport_hobby
    fact_key = Column(String, nullable=True, index=True)   # e.g. "hypertension", "weight", "metformin"
    fact_text = Column(EncryptedString, nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_user_verified = Column(Boolean, default=False, nullable=False)
    source_type = Column(String, nullable=False, default="chat")  # 'chat' | 'pdf' | 'profile' | 'user_edit'
    source_id = Column(String, nullable=True)
    source_excerpt = Column(EncryptedString, nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_patient_facts_user_dep_active", "user_id", "dependent_id", "is_active"),
    )

    user = orm_relationship("User", back_populates="patient_facts", foreign_keys=[user_id])
    dependent = orm_relationship("DependentProfile", back_populates="patient_facts", foreign_keys=[dependent_id])

    @hybrid_property
    def category(self):
        return self.fact_type

    @category.setter
    def category(self, val):
        self.fact_type = val

    @hybrid_property
    def fact_value(self):
        return self.fact_text

    @fact_value.setter
    def fact_value(self, val):
        self.fact_text = val

    @hybrid_property
    def source(self):
        return self.source_type

    @source.setter
    def source(self, val):
        self.source_type = val

    @hybrid_property
    def extracted_at(self):
        return self.created_at

    @hybrid_property
    def updated_at(self):
        return self.last_seen_at




class ChatChunk(Base):
    """
    Semantic memory chunks indexed from chat conversations for cross-session retrieval.
    """
    __tablename__ = "chat_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    dependent_id = Column(UUID(as_uuid=True), ForeignKey("dependent_profiles.id", ondelete="CASCADE"), nullable=True, index=True)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_text = Column(EncryptedString, nullable=False)
    chunk_index = Column(Integer, default=0, nullable=False)
    embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_chat_chunks_user_chat", "user_id", "chat_id"),
    )

    user = orm_relationship("User", back_populates="chat_chunks", foreign_keys=[user_id])
    dependent = orm_relationship("DependentProfile", back_populates="chat_chunks", foreign_keys=[dependent_id])
    chat = orm_relationship("Chat", back_populates="chat_chunks")


class ChatDocument(Base):
    """
    Join table linking Chat messages or sessions to multiple Documents.
    """
    __tablename__ = "chat_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "document_id", name="uq_chat_document"),
    )

    chat = orm_relationship("Chat", back_populates="chat_documents")
    document = orm_relationship("Document", back_populates="chat_documents")


class UploadJob(Base):
    """
    Persistent store for asynchronous PDF extraction and indexing jobs.
    Replaces in-memory job dictionaries for multi-instance Cloud Run resilience.
    """
    __tablename__ = "upload_jobs"

    id = Column(String(64), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False)
    document_id = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = orm_relationship("User", back_populates="upload_jobs")

