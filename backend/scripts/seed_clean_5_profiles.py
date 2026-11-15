#!/usr/bin/env python3
"""
MediSkye Clean 5-Profile Account Seeder (Zero PDFs, Zero Chats)
Performs:
1. 100% Clean Wipe of PostgreSQL/SQLite database tables (users, dependents, documents, chats, facts, etc.)
2. Deletion of all existing Firebase Auth users
3. Clean local index & upload directories
4. Creation of single master account: mediskye@test.com / MediSkye@2026!
5. Seeding of 5 distinct patient profiles with exact heights, weights, and durable clinical facts
6. Strict assertion that documents == 0 and chats == 0
"""

import os
import sys
import shutil
import asyncio
from datetime import date, datetime, UTC
import uuid

# Set up paths so app imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text, select, func
from app.db.database import AsyncSessionLocal, engine
from app.db.models import (
    User,
    DependentProfile,
    Document,
    Chat,
    ChatChunk,
    ChatDocument,
    PatientFact,
    UploadJob,
    AuditLog,
)
from app.core.auth import get_password_hash
from app.core.clinical import compute_bmi_info
import firebase_admin
from firebase_admin import auth as fb_auth, credentials


def utcnow():
    return datetime.now(UTC)


def init_firebase():
    if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    if not firebase_admin._apps:
        candidate_keys = [
            os.path.expanduser(r"~\Downloads\service-acc-key.json"),
            os.path.expanduser(r"~\OneDrive\Documents\service-acc-key.json"),
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "",
        ]
        for key_path in candidate_keys:
            if key_path and os.path.exists(key_path):
                try:
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred, options={"projectId": "mediskye-backend"})
                    print(f"Firebase Admin initialized with key: {key_path}")
                    return
                except Exception as e:
                    print(f"Key error ({key_path}): {e}")
        try:
            firebase_admin.initialize_app(options={"projectId": "mediskye-backend"})
            print("Firebase Admin initialized with default project options")
        except Exception:
            firebase_admin.initialize_app()
            print("Firebase Admin initialized fallback")


def clean_firebase_users():
    init_firebase()
    print("\n--- Cleaning Existing Firebase Auth Users ---")
    try:
        page = fb_auth.list_users()
        total_deleted = 0
        while page:
            for user in page.users:
                try:
                    fb_auth.delete_user(user.uid)
                    total_deleted += 1
                    print(f"  [Firebase] Deleted user: {user.email or user.uid}")
                except Exception as ex:
                    print(f"  [Firebase] Failed to delete user {user.uid}: {ex}")
            page = page.get_next_page()
        print(f"  [Firebase] Successfully wiped {total_deleted} Firebase Auth user(s).")
    except Exception as e:
        print(f"  [Firebase] Warning: Failed to query or delete Firebase Auth users: {e}")


def create_firebase_master_user(email: str, password: str, display_name: str) -> str:
    init_firebase()
    try:
        existing = fb_auth.get_user_by_email(email)
        fb_auth.delete_user(existing.uid)
    except Exception:
        pass

    user = fb_auth.create_user(
        email=email,
        password=password,
        display_name=display_name,
        email_verified=True,
    )
    print(f"  [Firebase] Created Master Account: {user.email} (UID: {user.uid})")
    return user.uid


def clean_local_storage():
    print("\n--- Cleaning Local Storage & Vector Indexes ---")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    dirs_to_clean = [
        os.path.join(base_dir, "vector_store"),
        os.path.join(base_dir, "uploads"),
        os.path.join(base_dir, "mediskye_indexes"),
        os.path.abspath(os.path.join(base_dir, "..", "mediskye_indexes")),
    ]
    for d in dirs_to_clean:
        if os.path.exists(d):
            try:
                for item in os.listdir(d):
                    item_path = os.path.join(d, item)
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                print(f"  Cleaned: {d}")
            except Exception as e:
                print(f"  Warning cleaning {d}: {e}")


async def seed_database():
    print("\n--- Ensuring DB Schema Columns Exist ---")
    async with engine.begin() as conn:
        def _migrate(sync_conn):
            try:
                sync_conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS weight_kg DOUBLE PRECISION"))
            except Exception:
                try:
                    sync_conn.execute(text("ALTER TABLE users ADD COLUMN weight_kg FLOAT"))
                except Exception:
                    pass

            dep_cols = [
                ("height_cm", "DOUBLE PRECISION", "FLOAT"),
                ("weight_kg", "DOUBLE PRECISION", "FLOAT"),
                ("diet_type", "VARCHAR", "VARCHAR"),
                ("activity_level", "VARCHAR", "VARCHAR"),
                ("occupation", "VARCHAR", "VARCHAR"),
                ("blood_type", "VARCHAR", "VARCHAR"),
                ("pre_existing_conditions", "VARCHAR", "VARCHAR"),
                ("known_allergies", "VARCHAR", "VARCHAR"),
                ("current_medications", "VARCHAR", "VARCHAR"),
            ]
            for col_name, pg_type, sqlite_type in dep_cols:
                try:
                    sync_conn.execute(text(f"ALTER TABLE dependent_profiles ADD COLUMN IF NOT EXISTS {col_name} {pg_type}"))
                except Exception:
                    try:
                        sync_conn.execute(text(f"ALTER TABLE dependent_profiles ADD COLUMN {col_name} {sqlite_type}"))
                    except Exception:
                        pass
        await conn.run_sync(_migrate)
    print("  Schema columns verified on live database.")

    print("\n--- Wiping Database Tables Clean ---")
    async with AsyncSessionLocal() as session:
        # Delete rows in dependency order
        tables = [
            "chat_chunks",
            "chat_documents",
            "chats",
            "patient_facts",
            "upload_jobs",
            "audit_logs",
            "documents",
            "dependent_profiles",
            "users",
        ]
        for tbl in tables:
            try:
                await session.execute(text(f"DELETE FROM {tbl}"))
            except Exception as e:
                print(f"  Table delete {tbl}: {e}")
        await session.commit()
    print("  All database tables truncated.")

    print("\n--- Seeding Master User & 5 Clinical Profiles ---")
    async with AsyncSessionLocal() as session:
        # 1. Master User: Aditya Sharma (self)
        master_user = User(
            id=uuid.uuid4(),
            email="mediskye@test.com",
            hashed_password=get_password_hash("MediSkye@2026!"),
            full_name="Aditya Sharma",
            biological_sex="Male",
            date_of_birth=date(2000, 5, 15),
            height_cm=178.0,
            weight_kg=72.0,
            diet_type="vegetarian",
            activity_level="very_active",
            occupation="Computer Science Graduate Student",
            pre_existing_conditions="None",
            known_allergies="Dust mites (mild), Pollen (seasonal)",
            current_medications="None",
            phi_consent_granted=True,
            consent_timestamp=utcnow(),
            memory_consent_granted=True,
            language_preference="English",
        )
        session.add(master_user)
        await session.flush()

        # 2. Dependent Profile 1: Aarav Verma (Brother)
        dep_aarav = DependentProfile(
            id=uuid.uuid4(),
            user_id=master_user.id,
            relationship="Brother",
            full_name="Aarav Verma",
            biological_sex="Male",
            date_of_birth=date(1999, 8, 20),
            height_cm=180.0,
            weight_kg=78.0,
            diet_type="vegetarian",
            activity_level="very_active",
            occupation="Product Designer",
            pre_existing_conditions="Allergic Rhinitis",
            current_medications="Creatine Monohydrate 5g/day, Vitamin D3 2000 IU/day",
            known_allergies="Dust mites",
        )
        session.add(dep_aarav)

        # 3. Dependent Profile 2: Anjali Verma (Sister)
        dep_anjali = DependentProfile(
            id=uuid.uuid4(),
            user_id=master_user.id,
            relationship="Sister",
            full_name="Anjali Verma",
            biological_sex="Female",
            date_of_birth=date(2003, 11, 10),
            height_cm=163.0,
            weight_kg=68.0,
            diet_type="vegetarian",
            activity_level="light",
            occupation="Marketing Manager",
            pre_existing_conditions="Mild fatigue on exertion, cold intolerance",
            current_medications="Biotin 5000 mcg, Multivitamin",
            known_allergies="Penicillin (causes hives)",
        )
        session.add(dep_anjali)

        # 4. Dependent Profile 3: Imran Qureshi (Uncle)
        dep_imran = DependentProfile(
            id=uuid.uuid4(),
            user_id=master_user.id,
            relationship="Uncle",
            full_name="Imran Qureshi",
            biological_sex="Male",
            date_of_birth=date(1973, 4, 12),
            height_cm=174.0,
            weight_kg=84.0,
            diet_type="non_vegetarian",
            activity_level="moderate",
            occupation="Civil Engineer",
            pre_existing_conditions="Borderline Hypertension (136/88 mmHg)",
            current_medications="Amlodipine 5mg once daily",
            known_allergies="Sulfa drugs",
        )
        session.add(dep_imran)

        # 5. Dependent Profile 4: Harish Menon (Father)
        dep_harish = DependentProfile(
            id=uuid.uuid4(),
            user_id=master_user.id,
            relationship="Father",
            full_name="Harish Menon",
            biological_sex="Male",
            date_of_birth=date(1964, 2, 28),
            height_cm=170.0,
            weight_kg=86.0,
            diet_type="mixed",
            activity_level="sedentary",
            occupation="Retired Bank Officer",
            pre_existing_conditions="Type 2 Diabetes Mellitus, Essential Hypertension",
            current_medications="Metformin 500mg twice daily, Telmisartan 40mg once daily",
            known_allergies="Ibuprofen / NSAIDs (causes severe gastric discomfort / reflux)",
        )
        session.add(dep_harish)
        await session.flush()

        # Seed durable Memory Vault facts for each profile
        facts = [
            # Profile 1: Aditya Sharma (self)
            PatientFact(
                user_id=master_user.id,
                dependent_id=None,
                fact_type="lifestyle",
                fact_key="diet",
                fact_text="Eats a vegetarian lacto-ovo diet rich in legumes, paneer, and whey protein.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=None,
                fact_type="lifestyle",
                fact_key="exercise",
                fact_text="Engages in strength training and hypertrophy weightlifting 4 days per week.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=None,
                fact_type="allergy",
                fact_key="allergic_rhinitis",
                fact_text="Mild allergic rhinitis triggered by seasonal tree pollen and dust mites.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=None,
                fact_type="clinical",
                fact_key="vital_signs",
                fact_text="Baseline blood pressure historically normal (~118/76 mmHg) with resting heart rate around 62 bpm.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),

            # Profile 2: Aarav Verma (Brother)
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_aarav.id,
                fact_type="lifestyle",
                fact_key="diet_supplements",
                fact_text="Vegetarian diet with daily creatine monohydrate supplementation (5g) and regular gym workouts.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_aarav.id,
                fact_type="clinical",
                fact_key="allergic_rhinitis",
                fact_text="History of mild allergic rhinitis during seasonal weather transitions.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_aarav.id,
                fact_type="medication",
                fact_key="supplements",
                fact_text="Takes daily Vitamin D3 (2000 IU) and occasional fexofenadine for allergy flares.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_aarav.id,
                fact_type="lifestyle",
                fact_key="occupation",
                fact_text="Works as a senior product designer with high screen engagement.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),

            # Profile 3: Anjali Verma (Sister)
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_anjali.id,
                fact_type="clinical",
                fact_key="fatigue_cold_intolerance",
                fact_text="Reports intermittent daytime fatigue and cold intolerance; monitoring thyroid panels.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_anjali.id,
                fact_type="allergy",
                fact_key="penicillin_allergy",
                fact_text="Documented severe penicillin allergy resulting in urticaria and facial hives.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_anjali.id,
                fact_type="lifestyle",
                fact_key="activity_lifestyle",
                fact_text="Works long desk hours as a marketing manager; lightly active with occasional weekend walks.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_anjali.id,
                fact_type="medication",
                fact_key="vitamins",
                fact_text="Takes daily Biotin 5000 mcg and general women's multivitamin for nail and hair health.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),

            # Profile 4: Imran Qureshi (Uncle)
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_imran.id,
                fact_type="clinical",
                fact_key="borderline_hypertension",
                fact_text="Essential borderline hypertension under pharmacological control with Amlodipine 5mg daily.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_imran.id,
                fact_type="allergy",
                fact_key="sulfa_allergy",
                fact_text="Reported allergy to sulfonamide medications causing maculopapular rash.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_imran.id,
                fact_type="lifestyle",
                fact_key="diet_occupation",
                fact_text="Non-vegetarian diet; frequently travels across construction sites for civil engineering projects.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_imran.id,
                fact_type="medication",
                fact_key="antihypertensive",
                fact_text="Maintains adherence to once-daily Amlodipine 5mg taken in the mornings.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),

            # Profile 5: Harish Menon (Father)
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_harish.id,
                fact_type="clinical",
                fact_key="t2d_and_htn",
                fact_text="Diagnosed with Type 2 Diabetes Mellitus (HbA1c target < 7.0%) and Essential Hypertension.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_harish.id,
                fact_type="medication",
                fact_key="daily_prescriptions",
                fact_text="Maintains strict adherence to Metformin 500mg BID and Telmisartan 40mg OD.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_harish.id,
                fact_type="allergy",
                fact_key="nsaid_intolerance",
                fact_text="Severe gastrointestinal intolerance to oral NSAIDs (ibuprofen); requires paracetamol for analgesia.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
            PatientFact(
                user_id=master_user.id,
                dependent_id=dep_harish.id,
                fact_type="lifestyle",
                fact_key="retirement_activity",
                fact_text="Sedentary lifestyle post-retirement; walks 20 minutes in the mornings.",
                source_type="profile",
                is_active=True,
                is_user_verified=True,
            ),
        ]

        session.add_all(facts)
        await session.commit()

        # Assertions
        doc_count = await session.scalar(select(func.count(Document.id)))
        chat_count = await session.scalar(select(func.count(Chat.id)))
        chat_doc_count = await session.scalar(select(func.count(ChatDocument.id)))
        user_count = await session.scalar(select(func.count(User.id)))
        dep_count = await session.scalar(select(func.count(DependentProfile.id)))
        fact_count = await session.scalar(select(func.count(PatientFact.id)))

        print("\n--- Verifying Seeding State ---")
        print(f"  Users:        {user_count} (Expected: 1)")
        print(f"  Dependents:   {dep_count} (Expected: 4)")
        print(f"  PatientFacts: {fact_count} (Expected: >= 16)")
        print(f"  Documents:    {doc_count} (Expected: 0)")
        print(f"  Chats:        {chat_count} (Expected: 0)")
        print(f"  ChatDocs:     {chat_doc_count} (Expected: 0)")

        assert user_count == 1, f"Expected 1 user, got {user_count}"
        assert dep_count == 4, f"Expected 4 dependents, got {dep_count}"
        assert fact_count >= 16, f"Expected >= 16 facts, got {fact_count}"
        assert doc_count == 0, f"Expected 0 documents, got {doc_count}"
        assert chat_count == 0, f"Expected 0 chats, got {chat_count}"
        assert chat_doc_count == 0, f"Expected 0 chat documents, got {chat_doc_count}"

        print("\n==========================================================================================")
        print("MEDISKYE 5-PROFILE CLINICAL ACCOUNT SEED COMPLETE (0 PDFs, 0 CHATS)")
        print("==========================================================================================")
        profiles = [
            ("Main (self)", "Aditya Sharma", 24, "Male", 178.0, 72.0),
            ("Brother", "Aarav Verma", 26, "Male", 180.0, 78.0),
            ("Sister", "Anjali Verma", 22, "Female", 163.0, 68.0),
            ("Uncle", "Imran Qureshi", 52, "Male", 174.0, 84.0),
            ("Father", "Harish Menon", 61, "Male", 170.0, 86.0),
        ]
        print(f"{'Role':<14} {'Full Name':<16} {'Age':<5} {'Sex':<8} {'Height':<8} {'Weight':<8} {'Calculated BMI':<26}")
        print("-" * 90)
        for role, name, age, sex, h, w in profiles:
            bmi_res = compute_bmi_info(h, w)
            bmi_fmt = bmi_res["formatted"] if bmi_res else "N/A"
            print(f"{role:<14} {name:<16} {age:<5} {sex:<8} {h:<8.1f} {w:<8.1f} {bmi_fmt:<26}")
        print("==========================================================================================")


async def main():
    clean_firebase_users()
    create_firebase_master_user("mediskye@test.com", "MediSkye@2026!", "Aditya Sharma")
    clean_local_storage()
    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())
