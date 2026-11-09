import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import User, Document
from app.services.upload_jobs import is_stale_building, fail_stale_building_documents
from app.core.auth import get_password_hash, create_access_token
from app.main import app
from tests.conftest import TEST_PASSWORD

def _doc(status, minutes_old, aware=True):
    created = datetime.now(UTC) - timedelta(minutes=minutes_old)
    if not aware:
        created = created.replace(tzinfo=None)
    return SimpleNamespace(index_status=status, created_at=created)

def test_old_building_doc_is_stale():
    assert is_stale_building(_doc("building", 30))

def test_naive_timestamp_is_treated_as_utc():
    assert is_stale_building(_doc("building", 30, aware=False))

def test_fresh_building_doc_is_not_stale():
    assert not is_stale_building(_doc("building", 2))

@pytest.mark.parametrize("status", ["local_ready", "synced", "failed"])
def test_non_building_docs_are_never_stale(status):
    assert not is_stale_building(_doc(status, 120))

def test_missing_created_at_is_not_stale():
    assert not is_stale_building(SimpleNamespace(index_status="building", created_at=None))


@pytest.mark.asyncio
async def test_fail_stale_building_documents_db_sweep():
    uid = uuid.uuid4()
    doc_stale_id = uuid.uuid4()
    doc_fresh_id = uuid.uuid4()
    doc_ready_id = uuid.uuid4()

    now = datetime.now(UTC)
    t_30m_ago = now - timedelta(minutes=30)
    t_1m_ago = now - timedelta(minutes=1)

    async with AsyncSessionLocal() as session:
        user = User(
            id=uid,
            email=f"sweep_{uuid.uuid4().hex[:8]}@test.com",
            hashed_password=get_password_hash(TEST_PASSWORD),
        )
        session.add(user)

        doc_stale = Document(
            id=doc_stale_id,
            user_id=uid,
            filename="stale.pdf",
            index_status="building",
            created_at=t_30m_ago,
        )
        doc_fresh = Document(
            id=doc_fresh_id,
            user_id=uid,
            filename="fresh.pdf",
            index_status="building",
            created_at=t_1m_ago,
        )
        doc_ready = Document(
            id=doc_ready_id,
            user_id=uid,
            filename="ready.pdf",
            index_status="local_ready",
            created_at=t_30m_ago,
        )
        session.add_all([doc_stale, doc_fresh, doc_ready])
        await session.commit()

        updated_count = await fail_stale_building_documents(session=session)
        assert updated_count == 1

        res_stale = await session.execute(select(Document).filter(Document.id == doc_stale_id))
        assert res_stale.scalars().first().index_status == "failed"

        res_fresh = await session.execute(select(Document).filter(Document.id == doc_fresh_id))
        assert res_fresh.scalars().first().index_status == "building"

        res_ready = await session.execute(select(Document).filter(Document.id == doc_ready_id))
        assert res_ready.scalars().first().index_status == "local_ready"


@pytest.mark.asyncio
async def test_endpoint_query_building_stale_returns_422():
    uid = uuid.uuid4()
    user_email = f"query_stale_{uuid.uuid4().hex[:8]}@test.com"
    doc_id = uuid.uuid4()
    t_30m_ago = datetime.now(UTC) - timedelta(minutes=30)

    async with AsyncSessionLocal() as session:
        user = User(
            id=uid,
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        doc = Document(
            id=doc_id,
            user_id=uid,
            filename="stale.pdf",
            file_path=f"uploads/{user_email}/{doc_id}",
            index_status="building",
            created_at=t_30m_ago,
        )
        session.add(doc)
        await session.commit()

    token = create_access_token(data={"sub": user_email})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query",
            json={
                "query": "What are my results?",
                "document_id": str(doc_id),
            },
            headers=headers,
        )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_query_building_fresh_returns_503():
    uid = uuid.uuid4()
    user_email = f"query_fresh_{uuid.uuid4().hex[:8]}@test.com"
    doc_id = uuid.uuid4()
    t_1m_ago = datetime.now(UTC) - timedelta(minutes=1)

    async with AsyncSessionLocal() as session:
        user = User(
            id=uid,
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        doc = Document(
            id=doc_id,
            user_id=uid,
            filename="fresh.pdf",
            file_path=f"uploads/{user_email}/{doc_id}",
            index_status="building",
            created_at=t_1m_ago,
        )
        session.add(doc)
        await session.commit()

    token = create_access_token(data={"sub": user_email})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query",
            json={
                "query": "What are my results?",
                "document_id": str(doc_id),
            },
            headers=headers,
        )
    assert res.status_code == 503

