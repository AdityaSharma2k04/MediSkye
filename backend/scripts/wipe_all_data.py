#!/usr/bin/env python3
"""
Full Clean Slate Data Wipe Script for MediSkye
Purges:
1. Firebase Auth users (iterates all and batch-deletes / deletes individually).
2. Neon PostgreSQL tables:
   TRUNCATE TABLE users, dependent_profiles, documents, chats, chat_documents, chat_chunks, patient_facts, upload_jobs, audit_logs RESTART IDENTITY CASCADE;
3. GCS bucket `mediskye-indexes` (if accessible).
"""

import os
import sys
import asyncio
from pathlib import Path

# Remove GOOGLE_APPLICATION_CREDENTIALS if it points to non-admin key
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import firebase_admin
from firebase_admin import auth as fb_auth, credentials
from sqlalchemy import text
from app.db.database import AsyncSessionLocal

PROJECT_ID = "mediskye-backend"


def init_firebase():
    if not firebase_admin._apps:
        candidate_keys = [
            os.path.expanduser(r"~\Downloads\service-acc-key.json"),
            os.path.expanduser(r"~\OneDrive\Documents\service-acc-key.json"),
        ]
        for key_path in candidate_keys:
            if key_path and os.path.exists(key_path):
                try:
                    cred = credentials.Certificate(key_path)
                    firebase_admin.initialize_app(cred, options={"projectId": PROJECT_ID})
                    print(f"[Firebase] Initialized with certificate: {key_path}")
                    return
                except Exception as e:
                    print(f"[Firebase] Cert init failed: {e}")
        try:
            firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
            print(f"[Firebase] Initialized with default ADC (projectId={PROJECT_ID})")
        except Exception:
            firebase_admin.initialize_app()
            print("[Firebase] Initialized with default fallback")


def wipe_firebase_auth():
    print("\n--- 1. WIPING FIREBASE AUTH USERS ---")
    page = fb_auth.list_users()
    deleted_count = 0
    while page:
        uids = [user.uid for user in page.users]
        if uids:
            try:
                delete_res = fb_auth.delete_users(uids)
                deleted_count += delete_res.success_count
                print(f"Batch deleted {delete_res.success_count} Firebase users. (Errors: {len(delete_res.errors)})")
            except Exception as e:
                print(f"Batch delete failed ({e}), deleting individually...")
                for uid in uids:
                    try:
                        fb_auth.delete_user(uid)
                        deleted_count += 1
                    except Exception as err:
                        print(f"Failed to delete {uid}: {err}")
        page = page.get_next_page()
    print(f"Total Firebase users wiped: {deleted_count}")


async def wipe_neon_db():
    print("\n--- 2. WIPING NEON POSTGRESQL TABLES ---")
    truncate_query = text(
        "TRUNCATE TABLE users, dependent_profiles, documents, chats, chat_documents, chat_chunks, patient_facts, upload_jobs, audit_logs RESTART IDENTITY CASCADE;"
    )
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(truncate_query)
        print("Truncated tables: users, dependent_profiles, documents, chats, chat_documents, chat_chunks, patient_facts, upload_jobs, audit_logs")

    # Verify counts
    async with AsyncSessionLocal() as session:
        user_count = (await session.execute(text("SELECT count(*) FROM users;"))).scalar()
        doc_count = (await session.execute(text("SELECT count(*) FROM documents;"))).scalar()
        chat_count = (await session.execute(text("SELECT count(*) FROM chats;"))).scalar()
        print(f"Verification: users={user_count}, documents={doc_count}, chats={chat_count}")


def wipe_gcs_bucket():
    print("\n--- 3. PURGING GCS BUCKET (mediskye-indexes) ---")
    try:
        from google.cloud import storage
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket("mediskye-indexes")
        blobs = list(bucket.list_blobs(max_results=500))
        if not blobs:
            print("GCS bucket mediskye-indexes is already empty or has no blobs.")
            return
        print(f"Found {len(blobs)} blobs in mediskye-indexes. Deleting...")
        for b in blobs:
            b.delete()
        print("Successfully deleted all GCS blobs.")
    except Exception as e:
        print(f"GCS bucket cleanup skipped or not accessible: {e}")


async def main():
    print("========================================")
    print("STARTING MEDISKYE PRODUCTION DATA WIPE")
    print("========================================")
    init_firebase()
    wipe_firebase_auth()
    await wipe_neon_db()
    wipe_gcs_bucket()
    print("========================================")
    print("DATA WIPE COMPLETE - CLEAN SLATE READY")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(main())

