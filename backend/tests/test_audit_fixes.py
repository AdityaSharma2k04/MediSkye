import uuid
import pytest
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.auth import get_password_hash, create_access_token
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, ChatDocument, ChatChunk, PatientFact, DependentProfile, AuditLog
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_query_unowned_document_returns_404():
    """Verify POST /query with an unowned document_id returns HTTP 404 Not Found."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email_a = f"owner_{uuid.uuid4().hex[:8]}@test.com"
        email_b = f"intruder_{uuid.uuid4().hex[:8]}@test.com"

        # Create User A & Doc A
        async with AsyncSessionLocal() as s:
            user_a = User(email=email_a, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            user_b = User(email=email_b, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add_all([user_a, user_b])
            await s.commit()
            await s.refresh(user_a)
            await s.refresh(user_b)

            doc_a = Document(user_id=user_a.id, filename="confidential.pdf", title="User A Confidential")
            s.add(doc_a)
            await s.commit()
            await s.refresh(doc_a)
            doc_a_id = doc_a.id

        # Login User B
        login_b = await ac.post("/login", data={"username": email_b, "password": TEST_PASSWORD})
        assert login_b.status_code == 200
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # User B queries User A's document -> MUST return 404 Not Found
        res_idor = await ac.post("/query", json={"query": "Tell me secrets", "document_id": str(doc_a_id)}, headers=headers_b)
        assert res_idor.status_code == 404
        assert res_idor.json()["detail"] == "Document not found"

        # User B queries invalid UUID format -> MUST return 404 Not Found
        res_invalid = await ac.post("/query", json={"query": "Tell me secrets", "document_id": "not-a-uuid"}, headers=headers_b)
        assert res_invalid.status_code == 404
        assert res_invalid.json()["detail"] == "Document not found"


@pytest.mark.asyncio
async def test_dependent_profile_deletion_cascade_all():
    """Verify DELETE /users/me/dependents/{id} purges all dependent documents, chats, chunks, and facts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"parent_{uuid.uuid4().hex[:8]}@test.com"
        user_id = None
        dep_id = None
        doc_id = None
        chat_id = None
        fact_id = None
        chunk_id = None

        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()
            await s.refresh(user)
            user_id = user.id

            dep = DependentProfile(user_id=user_id, relationship="Child", full_name="Junior")
            s.add(dep)
            await s.commit()
            await s.refresh(dep)
            dep_id = dep.id

            doc = Document(user_id=user_id, dependent_id=dep_id, filename="pediatric.pdf", title="Pediatric Growth")
            s.add(doc)
            await s.commit()
            await s.refresh(doc)
            doc_id = doc.id

            chat = Chat(user_id=user_id, document_id=doc_id, session_id=f"doc-{doc_id}", role="user", message="Pediatric growth chart")
            s.add(chat)
            await s.commit()
            await s.refresh(chat)
            chat_id = chat.id

            chunk = ChatChunk(id=uuid.uuid4(), user_id=user_id, chat_id=chat_id, dependent_id=dep_id, chunk_text="Growth percentile: 85th")
            fact = PatientFact(id=uuid.uuid4(), user_id=user_id, dependent_id=dep_id, fact_type="measurement", fact_text="85th percentile", source_type="chat", source_id=str(chat_id))
            cd = ChatDocument(chat_id=chat_id, document_id=doc_id)
            s.add_all([chunk, fact, cd])
            await s.commit()
            chunk_id = chunk.id
            fact_id = fact.id

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Delete dependent profile
        del_res = await ac.delete(f"/users/me/dependents/{dep_id}", headers=headers)
        assert del_res.status_code == 204

        # Verify full database cascade
        async with AsyncSessionLocal() as s:
            assert (await s.get(DependentProfile, dep_id)) is None
            assert (await s.get(Document, doc_id)) is None
            assert (await s.get(Chat, chat_id)) is None
            assert (await s.get(ChatChunk, chunk_id)) is None
            assert (await s.get(PatientFact, fact_id)) is None


@pytest.mark.asyncio
async def test_token_revocation_and_relogin():
    """Verify database-backed token_invalid_before revokes tokens on logout and resets on login."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"token_test_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as s:
            user = User(email=email, hashed_password=get_password_hash(TEST_PASSWORD), phi_consent_granted=True)
            s.add(user)
            await s.commit()

        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login.status_code == 200
        token_1 = login.json()["access_token"]
        headers_1 = {"Authorization": f"Bearer {token_1}"}

        # Valid before logout
        res_me = await ac.get("/users/me", headers=headers_1)
        assert res_me.status_code == 200

        # Logout
        res_logout = await ac.post("/logout", headers=headers_1)
        assert res_logout.status_code == 200

        # Revoked immediately (even without Redis via token_invalid_before)
        res_revoked = await ac.get("/users/me", headers=headers_1)
        assert res_revoked.status_code == 401
        assert "revoked" in res_revoked.json()["detail"].lower()

        # Immediate re-login works even within the same second
        login_2 = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login_2.status_code == 200
        token_2 = login_2.json()["access_token"]
        headers_2 = {"Authorization": f"Bearer {token_2}"}

        res_relogin = await ac.get("/users/me", headers=headers_2)
        assert res_relogin.status_code == 200

        # Old token remains revoked even after re-login (not revived!)
        res_old_token_revoked = await ac.get("/users/me", headers=headers_1)
        assert res_old_token_revoked.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_logout_fails():
    """Verify POST /logout rejects forged or unverified tokens with HTTP 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid / garbage token
        res_garbage = await ac.post("/logout", headers={"Authorization": "Bearer invalid.garbage.token"})
        assert res_garbage.status_code == 401

        # Missing token
        res_missing = await ac.post("/logout")
        assert res_missing.status_code == 401


@pytest.mark.asyncio
async def test_failed_login_audit_logs_hash_not_plaintext():
    """Verify failed login audit logs record a SHA-256 hash instead of plain email."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"failed_user_{uuid.uuid4().hex[:8]}@test.com"
        res = await ac.post("/login", data={"username": email, "password": "WrongPassword123!"})
        assert res.status_code == 401

        async with AsyncSessionLocal() as s:
            from sqlalchemy.future import select
            log_res = await s.execute(
                select(AuditLog).filter(AuditLog.action_type == "FAILED_LOGIN").order_by(AuditLog.timestamp.desc()).limit(1)
            )
            audit_entry = log_res.scalars().first()
            assert audit_entry is not None
            assert email not in (audit_entry.resource or "")
            assert "user_hash:" in (audit_entry.resource or "")

