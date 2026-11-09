import logging
import uuid
import pytest
import pytest_asyncio
import sqlalchemy as sa
from cryptography.fernet import Fernet

from app.db.database import AsyncSessionLocal
from app.db.models import (
    AuditLog,
    Chat,
    ChatChunk,
    ChatDocument,
    DependentProfile,
    Document,
    PatientFact,
    UploadJob,
    User,
)
from app.services.phi_backfill import (
    TARGETS,
    _raw_col,
    preflight_column_limits,
    preflight_key_matches,
    run_backfill,
)

METRICS = [
    {"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "range": "12.0 - 15.5", "status": "Normal"},
    {"test": "क्रिएटिनिन", "value": "0.9", "unit": "mg/dL", "range": "0.6 - 1.2", "status": "Normal"},
]


@pytest_asyncio.fixture(autouse=True)
async def clean_phi_tables():
    """Ensure tests in this module start with clean tables so stats counts match exactly."""
    async with AsyncSessionLocal() as session:
        for model in [
            ChatChunk,
            ChatDocument,
            AuditLog,
            PatientFact,
            UploadJob,
            Chat,
            Document,
            DependentProfile,
            User,
        ]:
            await session.execute(sa.delete(model))
        await session.commit()
    yield


async def _seed_legacy_rows():
    user_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"legacy_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
            full_name="Placeholder",
        )
        dep = DependentProfile(
            id=dep_id,
            user_id=user_id,
            relationship="Child",
            full_name="Placeholder",
        )
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="report.pdf",
            cached_metrics=None,
            cached_summary=None,
        )
        session.add_all([user, dep, doc])
        await session.commit()

    # Overwrite raw values with plaintext using Core updates that bypass the type
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(User.__table__)
            .where(User.id == user_id)
            .values(full_name=sa.literal("Aditya Sharma", type_=sa.Text()))
        )
        await session.execute(
            sa.update(DependentProfile.__table__)
            .where(DependentProfile.id == dep_id)
            .values(full_name=sa.literal("Riya Sharma", type_=sa.Text()))
        )
        await session.execute(
            sa.update(Document.__table__)
            .where(Document.id == doc_id)
            .values(
                cached_metrics=sa.literal(METRICS, type_=sa.JSON()),
                cached_summary=sa.literal("Hemoglobin is normal.", type_=sa.Text()),
            )
        )
        await session.commit()

    return user_id, dep_id, doc_id


@pytest.mark.asyncio
async def test_backfill_dry_run():
    user_id, dep_id, doc_id = await _seed_legacy_rows()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=False)

    stats_map = {s.label: s for s in stats}
    for label in ["documents.cached_metrics", "documents.cached_summary", "users.full_name", "dependent_profiles.full_name"]:
        assert stats_map[label].plaintext == 1
        assert stats_map[label].updated == 0

    # Assert NOTHING changed in raw values
    async with AsyncSessionLocal() as session:
        u_raw = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()
        d_raw = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()
        m_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

        assert u_raw == "Aditya Sharma"
        assert d_raw == "Riya Sharma"
        assert m_raw == METRICS
        assert s_raw == "Hemoglobin is normal."


@pytest.mark.asyncio
async def test_backfill_encrypt_apply():
    user_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"hindi_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
            full_name="Init",
        )
        dep = DependentProfile(
            id=dep_id,
            user_id=user_id,
            relationship="Mother",
            full_name="Init",
        )
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="hindi_report.pdf",
        )
        session.add_all([user, dep, doc])
        await session.commit()

    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(User.__table__)
            .where(User.id == user_id)
            .values(full_name=sa.literal("आदित्य शर्मा", type_=sa.Text()))
        )
        await session.execute(
            sa.update(DependentProfile.__table__)
            .where(DependentProfile.id == dep_id)
            .values(full_name=sa.literal("रिया शर्मा", type_=sa.Text()))
        )
        await session.execute(
            sa.update(Document.__table__)
            .where(Document.id == doc_id)
            .values(
                cached_metrics=sa.literal(METRICS, type_=sa.JSON()),
                cached_summary=sa.literal("मरीज का सारांश", type_=sa.Text()),
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=True)

    stats_map = {s.label: s for s in stats}
    for label in ["documents.cached_metrics", "documents.cached_summary", "users.full_name", "dependent_profiles.full_name"]:
        assert stats_map[label].plaintext == 1
        assert stats_map[label].updated == 1

    # Verify every raw value starts with gAAAA and is not plaintext
    async with AsyncSessionLocal() as session:
        u_raw = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()
        d_raw = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()
        m_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

        assert u_raw.startswith("gAAAA") and u_raw != "आदित्य शर्मा"
        assert d_raw.startswith("gAAAA") and d_raw != "रिया शर्मा"
        assert isinstance(m_raw, str) and m_raw.startswith("gAAAA") and m_raw != METRICS
        assert s_raw.startswith("gAAAA") and s_raw != "मरीज का सारांश"

    # ORM reads return the original plaintext
    async with AsyncSessionLocal() as session:
        u = (await session.execute(sa.select(User).where(User.id == user_id))).scalar_one()
        d = (await session.execute(sa.select(DependentProfile).where(DependentProfile.id == dep_id))).scalar_one()
        dc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()

        assert u.full_name == "आदित्य शर्मा"
        assert d.full_name == "रिया शर्मा"
        assert dc.cached_metrics == METRICS
        assert dc.cached_summary == "मरीज का सारांश"


@pytest.mark.asyncio
async def test_backfill_idempotent():
    user_id, dep_id, doc_id = await _seed_legacy_rows()

    # First encrypt apply
    async with AsyncSessionLocal() as session:
        await run_backfill(session, mode="encrypt", apply=True)

    # Capture raw values after first run
    async with AsyncSessionLocal() as session:
        u_raw1 = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()
        d_raw1 = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()
        m_raw1 = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw1 = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

    # Second encrypt apply
    async with AsyncSessionLocal() as session:
        stats2 = await run_backfill(session, mode="encrypt", apply=True)

    stats_map2 = {s.label: s for s in stats2}
    for label in ["documents.cached_metrics", "documents.cached_summary", "users.full_name", "dependent_profiles.full_name"]:
        assert stats_map2[label].updated == 0
        assert stats_map2[label].encrypted == 1

    # Verify raw values are unchanged between runs
    async with AsyncSessionLocal() as session:
        u_raw2 = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()
        d_raw2 = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()
        m_raw2 = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw2 = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

        assert u_raw1 == u_raw2
        assert d_raw1 == d_raw2
        assert m_raw1 == m_raw2
        assert s_raw1 == s_raw2


@pytest.mark.asyncio
async def test_backfill_mixed_already_encrypted_and_legacy():
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        # Row 1: created via ORM (already encrypted)
        u1 = User(
            id=user1_id,
            email=f"enc_{user1_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
            full_name="Encrypted User One",
        )
        # Row 2: created via ORM, then overwritten with plaintext
        u2 = User(
            id=user2_id,
            email=f"leg_{user2_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
            full_name="Init Plain",
        )
        session.add_all([u1, u2])
        await session.commit()

    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(User.__table__)
            .where(User.id == user2_id)
            .values(full_name=sa.literal("Legacy Plain User", type_=sa.Text()))
        )
        await session.commit()

    # Capture User 1's raw token before backfill
    async with AsyncSessionLocal() as session:
        u1_raw_before = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user1_id)
        )).scalar_one()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=True)

    user_stats = next(s for s in stats if s.label == "users.full_name")
    assert user_stats.total == 2
    assert user_stats.encrypted == 1
    assert user_stats.plaintext == 1
    assert user_stats.updated == 1

    # User 1 token must be byte-identical
    async with AsyncSessionLocal() as session:
        u1_raw_after = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user1_id)
        )).scalar_one()
        u2_raw_after = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user2_id)
        )).scalar_one()

        assert u1_raw_after == u1_raw_before
        assert u2_raw_after.startswith("gAAAA")
        assert u2_raw_after != "Legacy Plain User"


@pytest.mark.asyncio
async def test_backfill_revert_apply():
    user_id, dep_id, doc_id = await _seed_legacy_rows()

    # First encrypt apply
    async with AsyncSessionLocal() as session:
        await run_backfill(session, mode="encrypt", apply=True)

    # Verify they are encrypted
    async with AsyncSessionLocal() as session:
        m_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        assert isinstance(m_raw, str) and m_raw.startswith("gAAAA")

    # Revert apply
    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="revert", apply=True)

    stats_map = {s.label: s for s in stats}
    for label in ["documents.cached_metrics", "documents.cached_summary", "users.full_name", "dependent_profiles.full_name"]:
        assert stats_map[label].encrypted == 1
        assert stats_map[label].updated == 1

    # Raw values are plaintext again (cached_metrics raw is a list, not a str)
    async with AsyncSessionLocal() as session:
        u_raw = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()
        d_raw = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()
        m_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

        assert u_raw == "Aditya Sharma"
        assert d_raw == "Riya Sharma"
        assert isinstance(m_raw, list)
        assert m_raw == METRICS
        assert s_raw == "Hemoglobin is normal."

    # ORM reads return the original values
    async with AsyncSessionLocal() as session:
        u = (await session.execute(sa.select(User).where(User.id == user_id))).scalar_one()
        d = (await session.execute(sa.select(DependentProfile).where(DependentProfile.id == dep_id))).scalar_one()
        dc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()

        assert u.full_name == "Aditya Sharma"
        assert d.full_name == "Riya Sharma"
        assert dc.cached_metrics == METRICS
        assert dc.cached_summary == "Hemoglobin is normal."

    # Second revert reports updated == 0
    async with AsyncSessionLocal() as session:
        stats2 = await run_backfill(session, mode="revert", apply=True)

    stats_map2 = {s.label: s for s in stats2}
    for label in ["documents.cached_metrics", "documents.cached_summary", "users.full_name", "dependent_profiles.full_name"]:
        assert stats_map2[label].updated == 0


@pytest.mark.asyncio
async def test_backfill_undecryptable_token_skipped():
    foreign_fernet = Fernet(Fernet.generate_key())
    foreign_token = foreign_fernet.encrypt(b"secret from another key").decode("utf-8")

    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"undec_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
        )
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="corrupt.pdf",
        )
        session.add_all([user, doc])
        await session.commit()

    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(Document.__table__)
            .where(Document.id == doc_id)
            .values(cached_summary=sa.literal(foreign_token, type_=sa.Text()))
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=True)

    doc_summary_stats = next(s for s in stats if s.label == "documents.cached_summary")
    assert doc_summary_stats.undecryptable == 1
    assert doc_summary_stats.updated == 0

    # Ensure foreign token is NOT modified
    async with AsyncSessionLocal() as session:
        raw_val = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()
        assert raw_val == foreign_token


@pytest.mark.asyncio
async def test_backfill_nulls_counted_and_untouched():
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"null_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
        )
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="null_doc.pdf",
            cached_metrics=sa.null(),
            cached_summary=sa.null(),
        )
        session.add_all([user, doc])
        await session.commit()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=True)

    cm_stats = next(s for s in stats if s.label == "documents.cached_metrics")
    cs_stats = next(s for s in stats if s.label == "documents.cached_summary")
    assert cm_stats.null == 1
    assert cm_stats.updated == 0
    assert cs_stats.null == 1
    assert cs_stats.updated == 0

    # Verify raw values are still None
    async with AsyncSessionLocal() as session:
        m_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()
        s_raw = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()
        assert m_raw is None
        assert s_raw is None


@pytest.mark.asyncio
async def test_backfill_batching():
    u_ids = [uuid.uuid4() for _ in range(3)]

    async with AsyncSessionLocal() as session:
        users = [
            User(
                id=u_id,
                email=f"batch_{u_id.hex[:8]}@example.com",
                hashed_password="hashed_password",
                phi_consent_granted=True,
            )
            for u_id in u_ids
        ]
        session.add_all(users)
        await session.commit()

    async with AsyncSessionLocal() as session:
        for idx, u_id in enumerate(u_ids):
            await session.execute(
                sa.update(User.__table__)
                .where(User.id == u_id)
                .values(full_name=sa.literal(f"Batch User {idx}", type_=sa.Text()))
            )
        await session.commit()

    async with AsyncSessionLocal() as session:
        stats = await run_backfill(session, mode="encrypt", apply=True, batch_size=1)

    user_stats = next(s for s in stats if s.label == "users.full_name")
    assert user_stats.total == 3
    assert user_stats.updated == 3

    # All 3 raw values start with gAAAA
    async with AsyncSessionLocal() as session:
        for u_id in u_ids:
            raw_val = (await session.execute(
                sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == u_id)
            )).scalar_one()
            assert raw_val.startswith("gAAAA")


@pytest.mark.asyncio
async def test_backfill_no_phi_in_logs(caplog):
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    secret_name = "Aditya Secret Sharma"
    secret_summary = "Sensitive clinical summary text 98765"

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"log_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
        )
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="confidential.pdf",
        )
        session.add_all([user, doc])
        await session.commit()

    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(User.__table__)
            .where(User.id == user_id)
            .values(full_name=sa.literal(secret_name, type_=sa.Text()))
        )
        await session.execute(
            sa.update(Document.__table__)
            .where(Document.id == doc_id)
            .values(
                cached_metrics=sa.literal(METRICS, type_=sa.JSON()),
                cached_summary=sa.literal(secret_summary, type_=sa.Text()),
            )
        )
        await session.commit()

    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        async with AsyncSessionLocal() as session:
            await run_backfill(session, mode="encrypt", apply=True)

    # Assert none of the test plaintext strings appear in caplog.text
    assert secret_name not in caplog.text
    assert secret_summary not in caplog.text
    assert "Hemoglobin" not in caplog.text


@pytest.mark.asyncio
async def test_backfill_preflights():
    async with AsyncSessionLocal() as session:
        # 1. preflight_column_limits on sqlite returns empty list
        limits = await preflight_column_limits(session, "sqlite")
        assert limits == []

        # 2. preflight_key_matches on empty db returns None
        assert (await preflight_key_matches(session)) is None

        # 3. Create a chat row with a foreign-key token
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=f"preflight_{user_id.hex[:8]}@example.com",
            hashed_password="hashed_password",
            phi_consent_granted=True,
        )
        chat_id = uuid.uuid4()
        chat = Chat(
            id=chat_id,
            user_id=user_id,
            role="user",
            message="temp_message",
        )
        session.add_all([user, chat])
        await session.commit()

        foreign_fernet = Fernet(Fernet.generate_key())
        foreign_token = foreign_fernet.encrypt(b"alien message from other key").decode("utf-8")

        await session.execute(
            sa.update(Chat.__table__)
            .where(Chat.id == chat_id)
            .values(message=sa.literal(foreign_token, type_=sa.Text()))
        )
        await session.commit()

        key_problem = await preflight_key_matches(session)
        assert key_problem is not None
        assert "FERNET_KEY does not decrypt any sampled encrypted chat message" in key_problem
