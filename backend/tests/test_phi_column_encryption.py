import pytest
from cryptography.fernet import Fernet

from app.db.encryption import EncryptedJSON, EncryptedText

METRICS = [
    {"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "range": "12.0 - 15.5", "status": "Normal"},
    {"test": "क्रिएटिनिन", "value": "0.9", "unit": "mg/dL", "range": "0.6 - 1.2", "status": "Normal"},
]


def test_text_roundtrip_and_ciphertext():
    t = EncryptedText()
    token = t.process_bind_param("Aditya Sharma", None)
    assert token.startswith("gAAAA") and "Aditya" not in token
    assert t.process_result_value(token, None) == "Aditya Sharma"


@pytest.mark.parametrize("value", ["", "Hemoglobin is normal.", "मरीज का सारांश", "x" * 5000])
def test_text_roundtrip_values(value):
    t = EncryptedText()
    assert t.process_result_value(t.process_bind_param(value, None), None) == value


def test_text_none_and_legacy_plaintext_passthrough():
    t = EncryptedText()
    assert t.process_bind_param(None, None) is None
    assert t.process_result_value(None, None) is None
    assert t.process_result_value("Plain legacy name", None) == "Plain legacy name"


def test_text_undecryptable_token_is_none_not_ciphertext():
    t = EncryptedText()
    foreign = Fernet(Fernet.generate_key()).encrypt(b"secret").decode()
    assert t.process_result_value(foreign, None) is None


def test_json_roundtrip_and_ciphertext():
    j = EncryptedJSON()
    token = j.process_bind_param(METRICS, None)
    assert isinstance(token, str) and token.startswith("gAAAA")
    assert "Hemoglobin" not in token
    assert j.process_result_value(token, None) == METRICS


def test_json_empty_list_none_and_legacy_passthrough():
    j = EncryptedJSON()
    assert j.process_result_value(j.process_bind_param([], None), None) == []
    assert j.process_bind_param(None, None) is None
    assert j.process_result_value(None, None) is None
    assert j.process_result_value(METRICS, None) == METRICS       # legacy list
    assert j.process_result_value({"a": 1}, None) == {"a": 1}     # legacy dict


def test_json_undecryptable_token_is_none():
    j = EncryptedJSON()
    foreign = Fernet(Fernet.generate_key()).encrypt(b"[1]").decode()
    assert j.process_result_value(foreign, None) is None


# ---------------------------------------------------------------------------
# Part 2: DB Tests (User, DependentProfile, Document column encryption)
# ---------------------------------------------------------------------------
import uuid
import sqlalchemy as sa
from sqlalchemy.orm.attributes import flag_modified
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, Document


@pytest.mark.asyncio
async def test_db_encryption_token_and_orm_reload():
    user_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"phi_{user_id.hex[:8]}@example.com",
            hashed_password="test_hash_pw",
            full_name="Aditya Sharma",
            phi_consent_granted=True,
        )
        session.add(user)
        dep = DependentProfile(
            id=dep_id,
            user_id=user_id,
            relationship="Daughter",
            full_name="Riya Sharma",
        )
        session.add(dep)
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="blood_report.pdf",
            cached_metrics=METRICS,
            cached_summary="Hemoglobin is normal.",
        )
        session.add(doc)
        await session.commit()

    # Read RAW stored values bypassing the TypeDecorator
    async with AsyncSessionLocal() as session:
        raw_user_name = (await session.execute(
            sa.select(sa.type_coerce(User.__table__.c.full_name, sa.Text)).where(User.id == user_id)
        )).scalar_one()

        raw_dep_name = (await session.execute(
            sa.select(sa.type_coerce(DependentProfile.__table__.c.full_name, sa.Text)).where(DependentProfile.id == dep_id)
        )).scalar_one()

        raw_metrics = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_metrics, sa.JSON)).where(Document.id == doc_id)
        )).scalar_one()

        raw_summary = (await session.execute(
            sa.select(sa.type_coerce(Document.__table__.c.cached_summary, sa.Text)).where(Document.id == doc_id)
        )).scalar_one()

        assert isinstance(raw_user_name, str) and raw_user_name.startswith("gAAAA")
        assert "Aditya" not in raw_user_name

        assert isinstance(raw_dep_name, str) and raw_dep_name.startswith("gAAAA")
        assert "Riya" not in raw_dep_name

        assert isinstance(raw_metrics, str) and raw_metrics.startswith("gAAAA")
        assert "Hemoglobin" not in raw_metrics

        assert isinstance(raw_summary, str) and raw_summary.startswith("gAAAA")
        assert "Hemoglobin" not in raw_summary

    # Reload through ORM in a new session returns original plaintext values
    async with AsyncSessionLocal() as session:
        u = (await session.execute(sa.select(User).where(User.id == user_id))).scalar_one()
        d = (await session.execute(sa.select(DependentProfile).where(DependentProfile.id == dep_id))).scalar_one()
        dc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()

        assert u.full_name == "Aditya Sharma"
        assert d.full_name == "Riya Sharma"
        assert dc.cached_metrics == METRICS
        assert dc.cached_summary == "Hemoglobin is normal."


@pytest.mark.asyncio
async def test_db_legacy_plaintext_passthrough():
    user_id = uuid.uuid4()
    dep_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"legacy_{user_id.hex[:8]}@example.com",
            hashed_password="test_hash_pw",
            full_name="Temp Name",
            phi_consent_granted=True,
        )
        session.add(user)
        dep = DependentProfile(
            id=dep_id,
            user_id=user_id,
            relationship="Son",
            full_name="Temp Son",
        )
        session.add(dep)
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="legacy_doc.pdf",
            cached_metrics=None,
            cached_summary=None,
        )
        session.add(doc)
        await session.commit()

    # Overwrite raw values with PLAINTEXT using Core updates bypassing the type
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(User.__table__)
            .where(User.id == user_id)
            .values(full_name=sa.literal("Aditya Legacy Plain", type_=sa.Text()))
        )
        await session.execute(
            sa.update(DependentProfile.__table__)
            .where(DependentProfile.id == dep_id)
            .values(full_name=sa.literal("Riya Legacy Plain", type_=sa.Text()))
        )
        await session.execute(
            sa.update(Document.__table__)
            .where(Document.id == doc_id)
            .values(
                cached_metrics=sa.literal(METRICS, type_=sa.JSON()),
                cached_summary=sa.literal("legacy summary", type_=sa.Text()),
            )
        )
        await session.commit()

    # Reading through the ORM returns the plaintext without error
    async with AsyncSessionLocal() as session:
        u = (await session.execute(sa.select(User).where(User.id == user_id))).scalar_one()
        d = (await session.execute(sa.select(DependentProfile).where(DependentProfile.id == dep_id))).scalar_one()
        dc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()

        assert u.full_name == "Aditya Legacy Plain"
        assert d.full_name == "Riya Legacy Plain"
        assert dc.cached_metrics == METRICS
        assert dc.cached_summary == "legacy summary"


@pytest.mark.asyncio
async def test_db_filtering_cached_metrics_is_not_null():
    user_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"filter_{user_id.hex[:8]}@example.com",
            hashed_password="test_hash_pw",
            phi_consent_granted=True,
        )
        session.add(user)
        doc1 = Document(
            id=doc1_id,
            user_id=user_id,
            filename="has_metrics.pdf",
            cached_metrics=METRICS,
        )
        doc2 = Document(
            id=doc2_id,
            user_id=user_id,
            filename="no_metrics.pdf",
            cached_metrics=sa.null(),
        )
        session.add_all([doc1, doc2])
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = (await session.execute(
            sa.select(Document)
            .where(Document.id.in_([doc1_id, doc2_id]))
            .where(Document.cached_metrics.is_not(None))
        )).scalars().all()

        result_ids = [r.id for r in results]
        assert doc1_id in result_ids
        assert doc2_id not in result_ids


@pytest.mark.asyncio
async def test_db_mutation_path_and_empty_list():
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"mutate_{user_id.hex[:8]}@example.com",
            hashed_password="test_hash_pw",
            phi_consent_granted=True,
        )
        session.add(user)
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="mutate_test.pdf",
            cached_metrics=METRICS,
        )
        session.add(doc)
        await session.commit()

    new_metrics = [{"test": "WBC", "value": "6.0", "unit": "10^3/uL", "range": "4.0 - 11.0", "status": "Normal"}]
    async with AsyncSessionLocal() as session:
        doc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()
        doc.cached_metrics = new_metrics
        flag_modified(doc, "cached_metrics")
        await session.commit()

    async with AsyncSessionLocal() as session:
        doc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.cached_metrics == new_metrics

    # Set to empty list []
    async with AsyncSessionLocal() as session:
        doc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()
        doc.cached_metrics = []
        flag_modified(doc, "cached_metrics")
        await session.commit()

    async with AsyncSessionLocal() as session:
        doc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.cached_metrics == []
        assert doc.cached_metrics is not None


@pytest.mark.asyncio
async def test_db_empty_string_cached_summary_roundtrip():
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=f"empty_str_{user_id.hex[:8]}@example.com",
            hashed_password="test_hash_pw",
            phi_consent_granted=True,
        )
        session.add(user)
        doc = Document(
            id=doc_id,
            user_id=user_id,
            filename="empty_summary.pdf",
            cached_summary="",
        )
        session.add(doc)
        await session.commit()

    async with AsyncSessionLocal() as session:
        doc = (await session.execute(sa.select(Document).where(Document.id == doc_id))).scalar_one()
        assert doc.cached_summary == ""


