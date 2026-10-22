#!/usr/bin/env python3
"""
Compare real backend latency of two API hostnames with the same Firebase user.

Usage:
    python backend/scripts/host_compare.py \
        --hosts https://mediskye-backend.cloud.run https://mediskye-1095767703249.asia-southeast1.run.app

Measures, per host: GET /users/me, upload (POST /upload -> status COMPLETED),
cached GET /metrics, and POST /query TTFT (first SSE content chunk).
The temporary Firebase user and its data are deleted afterwards.
"""

import argparse
import asyncio
import os
import time
import uuid

import firebase_admin
import httpx
from firebase_admin import auth as fb_auth

FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


def ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 1)


async def probe_host(client: httpx.AsyncClient, host: str, headers: dict, pdf_bytes: bytes) -> dict:
    out: dict = {"host": host}

    me = []
    for _ in range(3):
        t0 = time.perf_counter()
        r = await client.get(f"{host}/users/me", headers=headers)
        me.append(ms(t0))
        r.raise_for_status()
    out["users_me_ms"] = me

    # Upload
    t0 = time.perf_counter()
    r = await client.post(
        f"{host}/upload",
        files={"file": ("host_compare.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
        timeout=60.0,
    )
    r.raise_for_status()
    out["upload_post_ms"] = ms(t0)
    job_id = r.json()["job_id"]
    doc_id = None
    polls = 0
    while time.perf_counter() - t0 < 120:
        await asyncio.sleep(0.5)
        polls += 1
        st = await client.get(f"{host}/upload/status/{job_id}", headers=headers)
        if st.status_code != 200:
            continue
        data = st.json()
        if str(data.get("status", "")).lower() == "completed":
            doc_id = data.get("document_id")
            break
        if str(data.get("status", "")).lower() == "failed":
            raise RuntimeError(data)
    out["upload_completed_ms"] = ms(t0)
    out["upload_polls"] = polls

    # Metrics: first call may extract; then measure cached hits
    await client.get(f"{host}/users/me/documents/{doc_id}/metrics", headers=headers, timeout=60.0)
    cached = []
    for _ in range(3):
        t0 = time.perf_counter()
        await client.get(f"{host}/users/me/documents/{doc_id}/metrics", headers=headers, timeout=60.0)
        cached.append(ms(t0))
    out["metrics_cached_ms"] = cached

    # Query TTFT (headers, first byte, first content chunk)
    t0 = time.perf_counter()
    first_byte = first_chunk = hdr = None
    async with client.stream(
        "POST",
        f"{host}/query",
        headers=headers,
        json={"session_id": str(doc_id), "query": "What are my abnormal values?", "language": "English"},
        timeout=120.0,
    ) as resp:
        hdr = ms(t0)
        async for text in resp.aiter_text():
            if first_byte is None and text.strip():
                first_byte = ms(t0)
            if first_chunk is None and '"chunk"' in text:
                first_chunk = ms(t0)
    out["query_headers_ms"] = hdr
    out["query_first_byte_ms"] = first_byte
    out["query_first_text_chunk_ms"] = first_chunk
    out["query_total_ms"] = ms(t0)
    return out


async def main(hosts):
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT_ID})

    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    pdf_path = os.path.join(root, "backend", "tests", "fixtures", "test_report.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    email = f"host_compare_{uuid.uuid4().hex[:10]}@example.com"
    password = f"HostCmp{uuid.uuid4().hex[:8]}!"
    user = fb_auth.create_user(email=email, password=password, email_verified=True)
    token = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}",
                json={"email": email, "password": password, "returnSecureToken": True},
            )
            r.raise_for_status()
            token = r.json()["idToken"]
            headers = {"Authorization": f"Bearer {token}"}
            for host in hosts:
                try:
                    res = await probe_host(client, host.rstrip("/"), headers, pdf_bytes)
                except Exception as e:  # keep comparing other hosts
                    res = {"host": host, "error": repr(e)}
                print("\n" + "=" * 70)
                for k, v in res.items():
                    print(f"  {k:28} {v}")
    finally:
        if token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.delete(f"{hosts[-1].rstrip('/')}/users/me", headers={"Authorization": f"Bearer {token}"})
            except Exception:
                pass
        try:
            fb_auth.delete_user(user.uid)
        except Exception:
            pass


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--hosts", nargs="+", required=True)
    asyncio.run(main(p.parse_args().hosts))
