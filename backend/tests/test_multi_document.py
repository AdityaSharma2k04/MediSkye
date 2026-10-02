import uuid
import pytest
from datetime import datetime, UTC
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.core.auth import get_password_hash
from app.db.database import AsyncSessionLocal
from app.db.models import User, Chat, Document, ChatDocument
from app.services.patient_memory import get_chat_documents
from app.rag.prompt_builder import build_prompt
from langchain_core.documents import Document as LCDocument
from tests.conftest import TEST_PASSWORD


async def create_user_and_headers(ac: AsyncClient, email: str) -> dict:
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_multi_document_attach_and_detach_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"multidoc_{uuid.uuid4().hex[:8]}@test.com"
        headers = await create_user_and_headers(ac, email)

        async with AsyncSessionLocal() as session:
            user_res = await session.execute(select(User).filter(User.email == email))
            user = user_res.scalars().first()

            doc1 = Document(user_id=user.id, filename="CBC_Jan_2026.pdf", title="CBC Report Jan")
            doc2 = Document(user_id=user.id, filename="Lipid_Aug_2026.pdf", title="Lipid Panel Aug")
            session.add_all([doc1, doc2])
            await session.commit()
            await session.refresh(doc1)
            await session.refresh(doc2)

            chat = Chat(user_id=user.id, role="user", message="Compare my CBC and Lipid tests.")
            session.add(chat)
            await session.commit()
            await session.refresh(chat)

            chat_id = chat.id
            doc1_id = doc1.id
            doc2_id = doc2.id

        # 1. Attach doc1 to chat via API
        res1 = await ac.post(f"/chats/{chat_id}/documents/{doc1_id}", headers=headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "attached"

        # 2. Attach doc2 to chat via API
        res2 = await ac.post(f"/chats/{chat_id}/documents/{doc2_id}", headers=headers)
        assert res2.status_code == 200

        # 3. GET /chats/{chat_id}/documents -> returns both
        res_list = await ac.get(f"/chats/{chat_id}/documents", headers=headers)
        assert res_list.status_code == 200
        docs_json = res_list.json()
        assert len(docs_json) == 2
        filenames = {d["filename"] for d in docs_json}
        assert "CBC_Jan_2026.pdf" in filenames
        assert "Lipid_Aug_2026.pdf" in filenames

        # Verify get_chat_documents returns both
        async with AsyncSessionLocal() as session:
            retrieved_docs = await get_chat_documents(chat_id, session)
            assert len(retrieved_docs) == 2

        # 4. Detach doc2 from chat via API
        res_del = await ac.delete(f"/chats/{chat_id}/documents/{doc2_id}", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "detached"

        # 5. GET /chats/{chat_id}/documents -> returns only doc1
        res_after = await ac.get(f"/chats/{chat_id}/documents", headers=headers)
        assert res_after.status_code == 200
        docs_after = res_after.json()
        assert len(docs_after) == 1
        assert docs_after[0]["filename"] == "CBC_Jan_2026.pdf"

        # Verify document itself was not deleted from DB
        async with AsyncSessionLocal() as session:
            doc2_check = await session.execute(select(Document).filter(Document.id == doc2_id))
            assert doc2_check.scalars().first() is not None


def test_multi_doc_prompt_cites_all_documents():
    chunk1 = LCDocument(
        page_content="Hemoglobin: 14.5 g/dL. Platelets: 250,000.",
        metadata={"source": "CBC_Jan_2026.pdf", "page": 1}
    )
    chunk2 = LCDocument(
        page_content="Total Cholesterol: 240 mg/dL. LDL: 160 mg/dL.",
        metadata={"source": "Lipid_Aug_2026.pdf", "page": 1}
    )

    prompt = build_prompt(
        user_query="How do my CBC and Lipid panels compare?",
        retrieved_docs=[chunk1, chunk2],
    )

    assert "<uploaded_documents>" in prompt
    assert 'name="CBC_Jan_2026.pdf"' in prompt
    assert 'name="Lipid_Aug_2026.pdf"' in prompt
    assert "Hemoglobin: 14.5" in prompt
    assert "Total Cholesterol: 240" in prompt
    assert 'Cite findings inline: "(from CBC_Jan_2026.pdf)"' in prompt
