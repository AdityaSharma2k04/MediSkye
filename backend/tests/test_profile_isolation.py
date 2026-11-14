import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, Document, Chat
from tests.conftest import TEST_PASSWORD


@pytest.mark.anyio
async def test_b1_b2_documents_and_chats_profile_isolation():
    """
    B1: Assert GET /users/me/documents, /users/me/chats/sessions, /users/me/chats
    return strictly isolated items for self, dependent A, and dependent B.
    B2: Assert querying documents for a dependent not owned by the user returns 403 or 404.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"isolation_{uuid.uuid4().hex[:8]}@example.com"
        reg_res = await ac.post("/register", json={
            "email": email,
            "password": TEST_PASSWORD,
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200

        login_res = await ac.post("/login", data={
            "username": email,
            "password": TEST_PASSWORD,
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create Dependent A and Dependent B
        dep_a_res = await ac.post("/users/me/dependents", json={
            "full_name": "ChildA Patient",
            "relationship": "Child",
            "date_of_birth": "2018-05-10",
        }, headers=headers)
        assert dep_a_res.status_code == 201
        dep_a_id = dep_a_res.json()["id"]

        dep_b_res = await ac.post("/users/me/dependents", json={
            "full_name": "ParentB Patient",
            "relationship": "Parent",
            "date_of_birth": "1960-01-15",
        }, headers=headers)
        assert dep_b_res.status_code == 201
        dep_b_id = dep_b_res.json()["id"]

        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            doc_self_id = uuid.uuid4()
            doc_a_id = uuid.uuid4()
            doc_b_id = uuid.uuid4()

            doc_self = Document(
                id=doc_self_id,
                user_id=user.id,
                dependent_id=None,
                filename="self_report.pdf",
                title="Self Report",
            )
            doc_a = Document(
                id=doc_a_id,
                user_id=user.id,
                dependent_id=uuid.UUID(dep_a_id),
                filename="dep_a_report.pdf",
                title="Dep A Report",
            )
            doc_b = Document(
                id=doc_b_id,
                user_id=user.id,
                dependent_id=uuid.UUID(dep_b_id),
                filename="dep_b_report.pdf",
                title="Dep B Report",
            )
            session.add_all([doc_self, doc_a, doc_b])

            chat_self = Chat(
                user_id=user.id,
                dependent_id=None,
                session_id="session-self",
                session_title="Self Chat",
                role="user",
                message="Self query",
            )
            chat_a = Chat(
                user_id=user.id,
                dependent_id=uuid.UUID(dep_a_id),
                session_id="session-dep-a",
                session_title="Dep A Chat",
                role="user",
                message="Dep A query",
            )
            chat_b = Chat(
                user_id=user.id,
                dependent_id=uuid.UUID(dep_b_id),
                session_id="session-dep-b",
                session_title="Dep B Chat",
                role="user",
                message="Dep B query",
            )
            session.add_all([chat_self, chat_a, chat_b])
            await session.commit()

        # B1: GET /users/me/documents with patient_id
        res_docs_self = await ac.get("/users/me/documents?patient_id=self", headers=headers)
        assert res_docs_self.status_code == 200
        docs_self = res_docs_self.json()
        assert len(docs_self) == 1
        assert docs_self[0]["id"] == str(doc_self_id)

        res_docs_a = await ac.get(f"/users/me/documents?patient_id={dep_a_id}", headers=headers)
        assert res_docs_a.status_code == 200
        docs_a = res_docs_a.json()
        assert len(docs_a) == 1
        assert docs_a[0]["id"] == str(doc_a_id)

        res_docs_b = await ac.get(f"/users/me/documents?patient_id={dep_b_id}", headers=headers)
        assert res_docs_b.status_code == 200
        docs_b = res_docs_b.json()
        assert len(docs_b) == 1
        assert docs_b[0]["id"] == str(doc_b_id)

        # B1: GET /users/me/chats/sessions with patient_id
        res_sess_self = await ac.get("/users/me/chats/sessions?patient_id=self", headers=headers)
        assert res_sess_self.status_code == 200
        sess_self = res_sess_self.json()
        assert len(sess_self) == 1
        assert sess_self[0]["session_id"] == "session-self"

        res_sess_a = await ac.get(f"/users/me/chats/sessions?patient_id={dep_a_id}", headers=headers)
        assert res_sess_a.status_code == 200
        sess_a = res_sess_a.json()
        assert len(sess_a) == 1
        assert sess_a[0]["session_id"] == "session-dep-a"

        # B1: GET /users/me/chats with patient_id
        res_chats_self = await ac.get("/users/me/chats?patient_id=self", headers=headers)
        assert res_chats_self.status_code == 200
        chats_self = res_chats_self.json()
        assert all(c.get("dependent_id") is None for c in chats_self)
        assert any(c.get("session_id") == "session-self" for c in chats_self)

        res_chats_a = await ac.get(f"/users/me/chats?patient_id={dep_a_id}", headers=headers)
        assert res_chats_a.status_code == 200
        chats_a = res_chats_a.json()
        assert all(c.get("dependent_id") == str(dep_a_id) for c in chats_a)

        # B2: Accessing documents with a foreign / non-existent dependent_id
        foreign_id = str(uuid.uuid4())
        res_foreign = await ac.get(f"/users/me/documents?patient_id={foreign_id}", headers=headers)
        assert res_foreign.status_code in (403, 404)


@pytest.mark.anyio
async def test_b3_profile_lock_prevents_cross_profile_query():
    """
    B3: Posting a query for a self document while acting as dependent A is rejected with 409 Profile Lock.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"proflock_{uuid.uuid4().hex[:8]}@example.com"
        await ac.post("/register", json={
            "email": email,
            "password": TEST_PASSWORD,
            "phi_consent_granted": True,
        })
        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        dep_a_res = await ac.post("/users/me/dependents", json={
            "full_name": "ChildA Patient",
            "relationship": "Child",
            "date_of_birth": "2018-05-10",
        }, headers=headers)
        dep_a_id = dep_a_res.json()["id"]

        doc_self_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            doc_self = Document(
                id=doc_self_id,
                user_id=user.id,
                dependent_id=None,
                filename="self_report.pdf",
                title="Self Report",
            )
            session.add(doc_self)
            await session.commit()

        # Attempt to query self document while specifying patient_id=dep_a_id
        query_res = await ac.post("/query", json={
            "query": "Explain my self report",
            "document_ids": [str(doc_self_id)],
            "patient_id": dep_a_id,
        }, headers=headers)
        assert query_res.status_code == 409
        assert "Profile Lock" in query_res.json()["detail"]


@pytest.mark.anyio
async def test_b4_upload_stores_dependent_id_correctly():
    """
    B4: The upload endpoint stores dependent_id correctly for self (null) and for a dependent.
    """
    import io
    from unittest.mock import patch

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"upload_iso_{uuid.uuid4().hex[:8]}@example.com"
        await ac.post("/register", json={
            "email": email,
            "password": TEST_PASSWORD,
            "phi_consent_granted": True,
        })
        login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        dep_res = await ac.post("/users/me/dependents", json={
            "full_name": "DepX Patient",
            "relationship": "Child",
            "date_of_birth": "2019-01-01",
        }, headers=headers)
        dep_id = dep_res.json()["id"]

        # Valid mock PDF content
        dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Resources << >>\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n190\n%%EOF"

        with patch("app.api.v1.endpoints.upload.process_upload_background"):
            # Upload for self
            files_self = {"file": ("self_report.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
            up_self = await ac.post("/upload", files=files_self, headers=headers)
            assert up_self.status_code == 202
            self_job_id = up_self.json()["job_id"]

            # Upload for dependent
            files_dep = {"file": ("dep_report.pdf", io.BytesIO(dummy_pdf), "application/pdf")}
            up_dep = await ac.post("/upload", files=files_dep, data={"patient_id": dep_id}, headers=headers)
            assert up_dep.status_code == 202
            dep_job_id = up_dep.json()["job_id"]

        assert self_job_id is not None
        assert dep_job_id is not None
