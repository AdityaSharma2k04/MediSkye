import uuid
from datetime import datetime, timedelta, UTC
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.core.auth import get_password_hash
from app.db.models import (
    User,
    Document,
    Chat,
    ChatDocument,
    ChatChunk,
    PatientFact,
    DependentProfile,
    UploadJob,
)
from app.services.clinical_units import is_sample_document
from app.services.fact_persistence import process_document_memory_extraction
from tests.conftest import TEST_PASSWORD


async def create_user_and_headers(ac: AsyncClient, email: str, memory_consent: bool = True) -> tuple[dict, uuid.UUID]:
    user_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
            memory_consent_granted=memory_consent,
            pre_existing_conditions="Type 2 Diabetes",
            current_medications="Metformin 500mg",
            known_allergies="Penicillin",
            blood_type="O+",
            diet_type="vegetarian",
            activity_level="moderate",
            occupation="Software Engineer",
            height_cm=175.5,
            biological_sex="Male",
        )
        session.add(user)
        await session.commit()

    login_res = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.mark.asyncio
async def test_global_delete_all_chats_wipes_self_and_all_dependents():
    """
    Test 1: DELETE /users/me/chats with no patient_id deletes chats, documents,
    chunks, and facts across Self AND all dependents.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"global_purge_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_headers(ac, email)

        dep_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            dep = DependentProfile(
                id=dep_id,
                user_id=user_id,
                full_name="Child Profile",
                relationship="Child",
                diet_type="omnivore",
                pre_existing_conditions="Asthma",
            )
            session.add(dep)

            # Self data
            doc_self = Document(id=uuid.uuid4(), user_id=user_id, filename="self_report.pdf", title="Self Report")
            chat_self = Chat(id=uuid.uuid4(), user_id=user_id, message="Self query", role="user")
            fact_self = PatientFact(
                id=uuid.uuid4(), user_id=user_id, fact_text="Self fact", fact_type="condition",
                fact_value="Condition X", confidence=0.9, is_active=True, source_type="chat"
            )
            session.add_all([doc_self, chat_self, fact_self])

            # Dependent data
            doc_dep = Document(id=uuid.uuid4(), user_id=user_id, dependent_id=dep_id, filename="dep_report.pdf", title="Dep Report")
            chat_dep = Chat(id=uuid.uuid4(), user_id=user_id, dependent_id=dep_id, message="Dep query", role="user")
            fact_dep = PatientFact(
                id=uuid.uuid4(), user_id=user_id, dependent_id=dep_id, fact_text="Dep fact",
                fact_type="medication", fact_value="Med Y", confidence=0.9, is_active=True, source_type="chat"
            )
            session.add_all([doc_dep, chat_dep, fact_dep])
            await session.commit()

        # Execute global reset (no patient_id filter)
        del_res = await ac.delete("/users/me/chats?clear_patient_context=true", headers=headers)
        assert del_res.status_code == 200
        data = del_res.json()
        assert data["status"] == "success"
        assert data["patient_context_cleared"] is True

        # Assert all documents, chats, facts wiped across both Self and dependent
        async with AsyncSessionLocal() as session:
            docs = (await session.execute(select(Document).filter(Document.user_id == user_id))).scalars().all()
            chats = (await session.execute(select(Chat).filter(Chat.user_id == user_id))).scalars().all()
            facts = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(docs) == 0
            assert len(chats) == 0
            assert len(facts) == 0

            # Assert clinical context was cleared
            user = (await session.execute(select(User).filter(User.id == user_id))).scalars().first()
            assert user.pre_existing_conditions is None
            assert user.diet_type is None


@pytest.mark.asyncio
async def test_per_profile_reset_wipes_only_target_profile_without_deleting_profile():
    """
    Test 2: DELETE /users/me/chats?patient_id={dep1.id}&clear_patient_context=false
    deletes dep1's chats, documents, and facts while keeping dep1's DependentProfile
    (and its demographic/clinical fields) intact, AND leaving Self and dep2 untouched.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"per_profile_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_headers(ac, email)

        dep1_id = uuid.uuid4()
        dep2_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            dep1 = DependentProfile(
                id=dep1_id,
                user_id=user_id,
                full_name="Dep One",
                relationship="Daughter",
                diet_type="vegan",
                pre_existing_conditions="Asthma",
            )
            dep2 = DependentProfile(
                id=dep2_id,
                user_id=user_id,
                full_name="Dep Two",
                relationship="Son",
                diet_type="vegetarian",
                pre_existing_conditions="Eczema",
            )
            session.add_all([dep1, dep2])

            # Self data
            doc_self = Document(id=uuid.uuid4(), user_id=user_id, filename="self_report.pdf", title="Self Report")
            chat_self = Chat(id=uuid.uuid4(), user_id=user_id, message="Self query", role="user")
            fact_self = PatientFact(
                id=uuid.uuid4(), user_id=user_id, fact_text="Self fact", fact_type="condition",
                fact_value="Condition A", confidence=0.9, is_active=True, source_type="chat"
            )

            # Dep1 data
            doc_dep1 = Document(id=uuid.uuid4(), user_id=user_id, dependent_id=dep1_id, filename="dep1_report.pdf", title="Dep 1 Report")
            chat_dep1 = Chat(id=uuid.uuid4(), user_id=user_id, dependent_id=dep1_id, message="Dep1 query", role="user")
            fact_dep1 = PatientFact(
                id=uuid.uuid4(), user_id=user_id, dependent_id=dep1_id, fact_text="Dep1 fact",
                fact_type="medication", fact_value="Inhaler", confidence=0.9, is_active=True, source_type="chat"
            )

            # Dep2 data
            doc_dep2 = Document(id=uuid.uuid4(), user_id=user_id, dependent_id=dep2_id, filename="dep2_report.pdf", title="Dep 2 Report")
            chat_dep2 = Chat(id=uuid.uuid4(), user_id=user_id, dependent_id=dep2_id, message="Dep2 query", role="user")
            fact_dep2 = PatientFact(
                id=uuid.uuid4(), user_id=user_id, dependent_id=dep2_id, fact_text="Dep2 fact",
                fact_type="allergy", fact_value="Pollen", confidence=0.9, is_active=True, source_type="chat"
            )

            session.add_all([doc_self, chat_self, fact_self, doc_dep1, chat_dep1, fact_dep1, doc_dep2, chat_dep2, fact_dep2])
            await session.commit()

        # Reset chats & memory for Dep 1 ONLY without clearing clinical setup
        del_res = await ac.delete(f"/users/me/chats?patient_id={dep1_id}&clear_patient_context=false", headers=headers)
        assert del_res.status_code == 200

        async with AsyncSessionLocal() as session:
            # Dep 1 profile must be intact and clinical setup preserved
            dep1_db = (await session.execute(select(DependentProfile).filter(DependentProfile.id == dep1_id))).scalars().first()
            assert dep1_db is not None
            assert dep1_db.diet_type == "vegan"
            assert dep1_db.pre_existing_conditions == "Asthma"

            # Dep 1's chats, documents, facts must be 0
            dep1_docs = (await session.execute(select(Document).filter(Document.dependent_id == dep1_id))).scalars().all()
            dep1_chats = (await session.execute(select(Chat).filter(Chat.dependent_id == dep1_id))).scalars().all()
            dep1_facts = (await session.execute(select(PatientFact).filter(PatientFact.dependent_id == dep1_id))).scalars().all()
            assert len(dep1_docs) == 0
            assert len(dep1_chats) == 0
            assert len(dep1_facts) == 0

            # Self and Dep 2 must be untouched
            self_docs = (await session.execute(select(Document).filter(Document.dependent_id.is_(None), Document.user_id == user_id))).scalars().all()
            self_facts = (await session.execute(select(PatientFact).filter(PatientFact.dependent_id.is_(None), PatientFact.user_id == user_id))).scalars().all()
            assert len(self_docs) == 1
            assert len(self_facts) == 1

            dep2_docs = (await session.execute(select(Document).filter(Document.dependent_id == dep2_id))).scalars().all()
            dep2_facts = (await session.execute(select(PatientFact).filter(PatientFact.dependent_id == dep2_id))).scalars().all()
            assert len(dep2_docs) == 1
            assert len(dep2_facts) == 1


@pytest.mark.asyncio
async def test_delete_dependent_profile_cascades_all_documents_chats_and_facts():
    """
    Test 3: DELETE /users/me/dependents/{dep_id} physically deletes all
    Document, Chat, ChatDocument, ChatChunk, UploadJob, and PatientFact rows
    belonging to that dependent.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"dep_cascade_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_headers(ac, email)

        dep_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        async with AsyncSessionLocal() as session:
            dep = DependentProfile(id=dep_id, user_id=user_id, full_name="Cascade Dep", relationship="Child")
            session.add(dep)

            doc = Document(id=doc_id, user_id=user_id, dependent_id=dep_id, filename="dep_cbc.pdf", title="Dep CBC")
            chat = Chat(id=chat_id, user_id=user_id, dependent_id=dep_id, document_id=doc_id, message="Dep question", role="user")
            session.add_all([doc, chat])
            await session.flush()

            cd = ChatDocument(chat_id=chat_id, document_id=doc_id)
            chunk = ChatChunk(chat_id=chat_id, user_id=user_id, dependent_id=dep_id, chunk_text="Chunk text")
            fact = PatientFact(
                id=uuid.uuid4(), user_id=user_id, dependent_id=dep_id, fact_text="Dep allergy",
                fact_type="allergy", fact_value="Peanuts", confidence=0.9, is_active=True, source_type="chat"
            )
            job = UploadJob(id=f"job-{uuid.uuid4().hex[:8]}", user_id=user_id, document_id=str(doc_id), status="completed")
            session.add_all([cd, chunk, fact, job])
            await session.commit()

        # Delete dependent
        del_res = await ac.delete(f"/users/me/dependents/{dep_id}", headers=headers)
        assert del_res.status_code == 204

        async with AsyncSessionLocal() as session:
            # Dep profile gone
            assert (await session.execute(select(DependentProfile).filter(DependentProfile.id == dep_id))).scalars().first() is None
            # All child records cascaded
            assert len((await session.execute(select(Document).filter(Document.dependent_id == dep_id))).scalars().all()) == 0
            assert len((await session.execute(select(Chat).filter(Chat.dependent_id == dep_id))).scalars().all()) == 0
            assert len((await session.execute(select(ChatDocument).filter(ChatDocument.document_id == doc_id))).scalars().all()) == 0
            assert len((await session.execute(select(ChatChunk).filter(ChatChunk.dependent_id == dep_id))).scalars().all()) == 0
            assert len((await session.execute(select(PatientFact).filter(PatientFact.dependent_id == dep_id))).scalars().all()) == 0
            assert len((await session.execute(select(UploadJob).filter(UploadJob.document_id == str(doc_id)))).scalars().all()) == 0


@pytest.mark.asyncio
async def test_sample_report_never_adds_facts_and_expires_after_24_hours():
    """
    Test 4:
    - Sample reports (e.g. filename='sample_blood_panel.pdf' or title='[Sample] ...')
      never add facts into PatientFact.
    - Sample documents backdated past 24 hours are automatically purged on
      GET /users/me/documents, while real reports > 24 hours are preserved.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"sample_ttl_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_headers(ac, email)

        sample_doc_id = uuid.uuid4()
        real_doc_id = uuid.uuid4()

        # 25 hours ago
        past_time = datetime.now(UTC) - timedelta(hours=25)

        async with AsyncSessionLocal() as session:
            # 1. Sample document
            sample_doc = Document(
                id=sample_doc_id,
                user_id=user_id,
                filename="Sample_Report.pdf",
                title="Sample Report: Lipid Panel",
                cached_metrics='[{"test": "Total Cholesterol", "value": "220", "unit": "mg/dL", "status": "High"}]',
                created_at=past_time,
            )
            # 2. Real document
            real_doc = Document(
                id=real_doc_id,
                user_id=user_id,
                filename="patient_actual_cbc.pdf",
                title="CBC Blood Panel",
                cached_metrics='[{"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "status": "Normal"}]',
                created_at=past_time,
            )
            session.add_all([sample_doc, real_doc])
            await session.commit()

        # Assert is_sample_document correctly tags sample document and rejects real document
        assert is_sample_document(sample_doc) is True
        assert is_sample_document(real_doc) is False
        assert is_sample_document("[Sample] Metabolic Panel") is True
        assert is_sample_document("sample_blood_report.pdf") is True

        # Assert process_document_memory_extraction returns 0 for sample report
        res = await process_document_memory_extraction(sample_doc_id, user_id)
        assert res["inserted"] == 0

        async with AsyncSessionLocal() as session:
            facts = (await session.execute(select(PatientFact).filter(PatientFact.user_id == user_id))).scalars().all()
            assert len(facts) == 0

        # Trigger auto-purge via GET /users/me/documents
        doc_list_res = await ac.get("/users/me/documents", headers=headers)
        assert doc_list_res.status_code == 200
        docs = doc_list_res.json()

        # The expired sample document (>24h) MUST have been purged
        doc_ids_returned = [d["id"] for d in docs]
        assert str(sample_doc_id) not in doc_ids_returned
        # The real document (>24h) MUST be preserved
        assert str(real_doc_id) in doc_ids_returned


@pytest.mark.asyncio
async def test_reassign_document_patient_and_biomarkers_v4():
    """
    Test PATCH /users/me/documents/{doc_id}/patient reassigns document, chats, and facts,
    and verify biomarker canonicalization and critical low potassium bucketing.
    """
    from app.rag.biomarkers import (
        canonical_biomarker_key,
        build_extracted_biomarkers_and_hints,
    )
    from app.services.clinical_units import canonical_biomarker_key as cu_canonical_key

    # 1. Biomarkers v4 verification
    assert canonical_biomarker_key("Anti-TG Antibodies") == "anti_tg"
    assert cu_canonical_key("Anti-TG Antibodies") == "anti_tg"
    assert canonical_biomarker_key("Cholesterol, Total") == "total_cholesterol"
    assert cu_canonical_key("Cholesterol, Total") == "cholesterol"

    # Critical low potassium (2.1 on 3.5 - 5.1) bucketed under low_markers
    potassium_fixture = [{"test": "Potassium", "value": "2.1", "unit": "mmol/L", "range": "3.5 - 5.1", "status": "Critical"}]
    res_hints = build_extracted_biomarkers_and_hints(potassium_fixture)
    assert "low_markers: Potassium" in res_hints
    assert "out_of_range_markers: Potassium" in res_hints

    # 2. PATCH /users/me/documents/{doc_id}/patient reassignment
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"reassign_{uuid.uuid4().hex[:8]}@test.com"
        headers, user_id = await create_user_and_headers(ac, email)

        dep_a_id = uuid.uuid4()
        dep_b_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        chat_id = uuid.uuid4()
        fact_id = uuid.uuid4()

        async with AsyncSessionLocal() as session:
            dep_a = DependentProfile(id=dep_a_id, user_id=user_id, full_name="Person A", relationship="Spouse")
            dep_b = DependentProfile(id=dep_b_id, user_id=user_id, full_name="Person B", relationship="Child")
            doc = Document(id=doc_id, user_id=user_id, dependent_id=dep_b_id, filename="thyroid_panel.pdf", title="Thyroid Panel")
            chat = Chat(id=chat_id, user_id=user_id, dependent_id=dep_b_id, document_id=doc_id, message="Explain Anti-TG", role="user")
            fact = PatientFact(
                id=fact_id,
                user_id=user_id,
                dependent_id=dep_b_id,
                source_id=str(doc_id),
                fact_text="Anti-TG elevated",
                fact_type="measurement",
                confidence=0.95,
                is_active=True,
                source_type="report",
            )
            session.add_all([dep_a, dep_b, doc, chat, fact])
            await session.commit()

        # Reassignment attempt must be rejected with HTTP 403 Forbidden (profile is locked)
        patch_res = await ac.patch(
            f"/users/me/documents/{doc_id}/patient",
            headers=headers,
            json={"patient_id": str(dep_a_id)},
        )
        assert patch_res.status_code == 403
        assert "permanently locked" in patch_res.json()["detail"]

        # Reassign to self must also be rejected with HTTP 403 Forbidden
        patch_self = await ac.patch(
            f"/users/me/documents/{doc_id}/patient",
            headers=headers,
            json={"patient_id": "self"},
        )
        assert patch_self.status_code == 403
        assert "permanently locked" in patch_self.json()["detail"]

        # Verify DB state remained untouched
        async with AsyncSessionLocal() as session:
            d_doc = await session.get(Document, doc_id)
            c_chat = await session.get(Chat, chat_id)
            f_fact = await session.get(PatientFact, fact_id)

            assert d_doc.dependent_id == dep_b_id
            assert c_chat.dependent_id == dep_b_id
            assert f_fact.dependent_id == dep_b_id

