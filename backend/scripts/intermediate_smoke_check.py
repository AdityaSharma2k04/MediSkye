#!/usr/bin/env python3
"""
Step 1 Intermediate Smoke Check Gate:
Performs a 3-run smoke latency check (upload + one /query) to verify Step 1 optimizations
prior to proceeding to Step 2.
"""

import sys
import os
import asyncio
import time
import uuid
import pymupdf as fitz
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat, DependentProfile
from app.rag.index_storage import delete_index_artifacts


def generate_sample_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Central Facility Laboratory - Diagnostic Report\n"
        "Patient: Smoke Test User. Sample ID: #SMOKE123.\n"
        "Hemoglobin: 14.8 g/dL (Reference Range: 12.0 - 15.5 g/dL) Normal.\n"
        "Total WBC: 6200 /uL (Reference: 4500 - 11000) Normal.\n"
        "Platelet Count: 240,000 /uL (Reference: 150,000 - 450,000) Normal.\n"
        "Total Cholesterol: 185 mg/dL (Reference: < 200 mg/dL) Desirable.\n"
    )
    return doc.tobytes()


async def run_smoke_check():
    print("=" * 65)
    print("STEP 1 INTERMEDIATE SMOKE CHECK GATE (3 RUNS)")
    print("=" * 65)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"smoke_step1_{uuid.uuid4().hex[:8]}@example.com"
        password = "SmokeTestPassword123!"

        reg_res = await ac.post("/register", json={
            "email": email,
            "password": password,
            "phi_consent_granted": True,
        })
        assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"

        login_res = await ac.post("/login", data={
            "username": email,
            "password": password,
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        pdf_bytes = generate_sample_pdf_bytes()
        runs_data = []

        for run_idx in range(1, 4):
            print(f"\n--- Smoke Run {run_idx}/3 ---")
            t_upload_start = time.perf_counter()
            upload_res = await ac.post(
                "/upload",
                files={"file": (f"smoke_report_{run_idx}.pdf", pdf_bytes, "application/pdf")},
                headers=headers,
            )
            assert upload_res.status_code == 202, f"Upload submission failed: {upload_res.text}"
            job_id = upload_res.json()["job_id"]

            doc_id = None
            poll_attempts = 0
            while poll_attempts < 30:
                poll_res = await ac.get(f"/upload/status/{job_id}", headers=headers)
                assert poll_res.status_code == 200
                st = poll_res.json().get("status")
                if st == "completed":
                    doc_id = poll_res.json()["document_id"]
                    break
                elif st == "failed":
                    raise RuntimeError(f"Upload job failed: {poll_res.json().get('error')}")
                await asyncio.sleep(0.3)
                poll_attempts += 1

            upload_total_ms = (time.perf_counter() - t_upload_start) * 1000.0
            assert doc_id is not None, "Upload job did not complete in time"
            print(f"  Upload + Indexing Complete: {upload_total_ms:.1f}ms (doc_id={doc_id})")

            # Execute 1 /query on the uploaded document
            t_query_start = time.perf_counter()
            ttft_ms = None
            stream_chunks = 0
            full_reply = ""

            query_res = await ac.post(
                "/query",
                json={
                    "session_id": str(doc_id),
                    "query": "What is my hemoglobin level and status?",
                },
                headers=headers,
            )
            assert query_res.status_code in (200, 204), f"Query failed with status {query_res.status_code}: {query_res.text}"

            async for line in query_res.aiter_lines():
                if line.startswith("data: ") and not line.startswith("data: [DONE]"):
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t_query_start) * 1000.0
                    stream_chunks += 1
                    try:
                        import json
                        chunk_obj = json.loads(line[6:])
                        if "chunk" in chunk_obj:
                            full_reply += chunk_obj["chunk"]
                    except Exception:
                        pass

            query_total_ms = (time.perf_counter() - t_query_start) * 1000.0
            print(f"  Query TTFT: {ttft_ms or query_total_ms:.1f}ms | Total Stream: {query_total_ms:.1f}ms ({stream_chunks} events)")

            runs_data.append({
                "run": run_idx,
                "upload_ms": upload_total_ms,
                "query_ttft_ms": ttft_ms or query_total_ms,
                "query_total_ms": query_total_ms,
                "doc_id": doc_id,
            })

        print("\n" + "=" * 65)
        print("INTERMEDIATE SMOKE CHECK SUMMARY TABLE")
        print("=" * 65)
        print(f"{'Run':<6} | {'Upload (Fast Path)':<20} | {'Query TTFT':<15} | {'Query Total':<15}")
        print("-" * 65)
        for r in runs_data:
            print(f"Run {r['run']:<2} | {r['upload_ms']:>16.1f} ms | {r['query_ttft_ms']:>11.1f} ms | {r['query_total_ms']:>11.1f} ms")
        print("-" * 65)

        avg_upload = sum(r["upload_ms"] for r in runs_data) / len(runs_data)
        avg_ttft = sum(r["query_ttft_ms"] for r in runs_data) / len(runs_data)
        avg_query = sum(r["query_total_ms"] for r in runs_data) / len(runs_data)
        print(f"Avg    | {avg_upload:>16.1f} ms | {avg_ttft:>11.1f} ms | {avg_query:>11.1f} ms")
        print("=" * 65)

        # Cleanup test user and artifacts
        print("\nCleaning up smoke test user and document artifacts...")
        del_res = await ac.delete("/users/me", headers=headers)
        print(f"User cleanup status: {del_res.status_code}")
        print("Smoke Check Gate PASSED successfully.\n")


if __name__ == "__main__":
    asyncio.run(run_smoke_check())
