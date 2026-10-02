"""
D2 / GDPR-HIPAA: deleting a user must cascade to every child row, while the
audit trail is preserved with ``user_id = NULL`` (never cascaded).

The test deliberately issues *raw SQL* (not an ORM delete) so that only the
database-level ``ON DELETE`` actions are exercised. ORM ``cascade="all,
delete-orphan"`` would mask a missing ``ondelete`` clause.
"""
import uuid

import pytest
import sqlalchemy as sa

from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import (
    AuditLog,
    Chat,
    ChatChunk,
    DependentProfile,
    Document,
    PatientFact,
    User,
)
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_delete_user_cascades_children_and_nulls_audit_log():
    user_id = uuid.uuid4()
    dependent_id = uuid.uuid4()
    document_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    fact_id = uuid.uuid4()
    audit_id = uuid.uuid4()

    # 1. Seed one row in every child table.
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                id=user_id,
                email=f"cascade_{uuid.uuid4().hex[:8]}@test.com",
                hashed_password=get_password_hash(TEST_PASSWORD),
                memory_consent_granted=True,
            )
        )
        session.add(
            DependentProfile(
                id=dependent_id,
                user_id=user_id,
                relationship="child",
                full_name="Cascade Child",
            )
        )
        session.add(
            Document(
                id=document_id,
                user_id=user_id,
                dependent_id=dependent_id,
                filename="lab_report.pdf",
                file_path="/tmp/lab_report",
            )
        )
        session.add(
            Chat(
                id=chat_id,
                user_id=user_id,
                document_id=document_id,
                role="user",
                message="What do my results mean?",
            )
        )
        session.add(
            ChatChunk(
                id=chunk_id,
                user_id=user_id,
                dependent_id=dependent_id,
                chat_id=chat_id,
                chunk_text="Hemoglobin 14.2 g/dL, within normal limits.",
            )
        )
        session.add(
            PatientFact(
                id=fact_id,
                user_id=user_id,
                dependent_id=dependent_id,
                fact_type="symptom",
                fact_text="Occasional headaches",
            )
        )
        session.add(
            AuditLog(
                id=audit_id,
                user_id=user_id,
                dependent_id=dependent_id,
                action_type="login",
                resource="/login",
            )
        )
        await session.commit()

    # 2. Guard: SQLite only honours ON DELETE when foreign_keys is enabled.
    async with AsyncSessionLocal() as session:
        fk_enabled = (await session.execute(sa.text("PRAGMA foreign_keys"))).scalar()
        assert fk_enabled == 1, "PRAGMA foreign_keys must be ON for cascade deletes"

        # Raw SQL delete (typed bindparam keeps UUID handling dialect-agnostic).
        delete_stmt = sa.text("DELETE FROM users WHERE id = :uid").bindparams(
            sa.bindparam("uid", type_=User.__table__.c.id.type)
        )
        await session.execute(delete_stmt, {"uid": user_id})
        await session.commit()

    # 3. All child rows must be gone.
    async with AsyncSessionLocal() as session:
        children = [
            (DependentProfile, dependent_id),
            (Document, document_id),
            (Chat, chat_id),
            (ChatChunk, chunk_id),
            (PatientFact, fact_id),
        ]
        for model, row_id in children:
            remaining = (
                await session.execute(sa.select(model).where(model.id == row_id))
            ).scalars().first()
            assert remaining is None, f"{model.__name__} should have been cascaded away"

        # 4. The audit log survives, detached from the deleted user.
        audit = (
            await session.execute(sa.select(AuditLog).where(AuditLog.id == audit_id))
        ).scalars().first()
        assert audit is not None, "audit_logs row must be preserved after user deletion"
        assert audit.user_id is None, "audit_logs.user_id must be SET NULL, not cascaded"
