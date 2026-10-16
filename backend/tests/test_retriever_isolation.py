import uuid
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.documents import Document as LCDocument

from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile, Document as DBDocument
from app.rag.retriever import retrieve_cross_document
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_retrieve_cross_document_isolation_self_vs_dependent():
    """
    Verify that retrieve_cross_document isolates documents:
    - dependent_id=None returns ONLY Self documents (dependent_id is None)
    - dependent_id=<uuid> returns ONLY the specified dependent's documents
    """
    email = f"retriever_iso_{uuid.uuid4().hex[:8]}@test.com"
    async with AsyncSessionLocal() as session:
        user = User(
            email=email,
            hashed_password="hashedpassword",
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        dependent = DependentProfile(
            user_id=user.id,
            relationship="Child",
            full_name="Alex Doe",
        )
        session.add(dependent)
        await session.commit()
        await session.refresh(dependent)

        doc_self = DBDocument(
            user_id=user.id,
            dependent_id=None,
            filename="self_report.pdf",
            file_path="dummy_path_self.index",
            title="Self Blood Test",
        )
        doc_dep = DBDocument(
            user_id=user.id,
            dependent_id=dependent.id,
            filename="dependent_report.pdf",
            file_path="dummy_path_dep.index",
            title="Dependent Pediatric Exam",
        )
        session.add_all([doc_self, doc_dep])
        await session.commit()
        await session.refresh(doc_self)
        await session.refresh(doc_dep)

        user_id = user.id
        dep_id = dependent.id
        self_doc_id = str(doc_self.id)
        dep_doc_id = str(doc_dep.id)

    def fake_retrieve(query, vectorstore, bm25_index, k=8):
        return [LCDocument(page_content=f"Report chunk for query: {query}", metadata={})]

    with (
        patch("os.path.exists", return_value=True),
        patch("app.rag.retriever.load_hybrid_index", return_value=(MagicMock(), MagicMock())),
        patch("app.rag.retriever.retrieve_relevant_docs", side_effect=fake_retrieve),
    ):
        async with AsyncSessionLocal() as session:
            # 1. Query as Self (dependent_id=None) -> only Self's doc should be retrieved
            results_self = await retrieve_cross_document(
                user_id=user_id,
                query="blood results",
                db=session,
                dependent_id=None,
            )
            doc_ids_self = {r.metadata.get("document_id") for r in results_self}
            assert self_doc_id in doc_ids_self, "Self document missing from Self retrieval"
            assert dep_doc_id not in doc_ids_self, "Dependent document leaked into Self retrieval"

            # 2. Query as Dependent (dependent_id=dep_id UUID) -> only Dependent's doc should be retrieved
            results_dep = await retrieve_cross_document(
                user_id=user_id,
                query="pediatric exam",
                db=session,
                dependent_id=dep_id,
            )
            doc_ids_dep = {r.metadata.get("document_id") for r in results_dep}
            assert dep_doc_id in doc_ids_dep, "Dependent document missing from Dependent retrieval"
            assert self_doc_id not in doc_ids_dep, "Self document leaked into Dependent retrieval"

            # 3. Query as Dependent with string UUID -> must also isolate properly
            results_dep_str = await retrieve_cross_document(
                user_id=user_id,
                query="pediatric exam",
                db=session,
                dependent_id=str(dep_id),
            )
            doc_ids_dep_str = {r.metadata.get("document_id") for r in results_dep_str}
            assert dep_doc_id in doc_ids_dep_str
            assert self_doc_id not in doc_ids_dep_str
