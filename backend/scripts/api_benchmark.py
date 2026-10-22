#!/usr/bin/env python3
"""
Direct Cloud Run API Benchmark for MediSkye
Measures direct Cloud Run API latencies (GET /health, GET /users/me, POST /query stream)
bypassing frontend browser rendering overhead.
Appends metrics to ./testing_log in the project root.
"""

import argparse
import asyncio
import datetime
import os
import sys
import time
import uuid
import httpx
import firebase_admin
from firebase_admin import auth as fb_auth

DEFAULT_API_URL = "https://mediskye-1095767703249.asia-southeast1.run.app"
DEFAULT_FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


def get_root_log_path() -> str:
    # Look for project root (parent of backend/scripts)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_candidate = os.path.abspath(os.path.join(current_dir, "..", ".."))
    return os.path.join(root_candidate, "testing_log")


def append_to_testing_log(section_text: str):
    log_path = get_root_log_path()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            existing_content = f.read().strip()

    header = f"==================================================\nMEDISKYE LATENCY LOG — [{now_str}]\n=================================================="

    if not existing_content:
        new_content = f"{header}\n\n{section_text}\n==================================================\n"
    else:
        # Strip trailing border if present
        lines = existing_content.splitlines()
        filtered = []
        for line in lines:
            if line.strip() == "==================================================" or "MEDISKYE LATENCY LOG" in line:
                continue
            filtered.append(line)
        
        body = "\n".join(filtered).strip()
        new_content = f"{header}\n\n{body}\n\n{section_text}\n==================================================\n"

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[api_benchmark] Log updated at: {log_path}")


def init_firebase():
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
        except Exception as e:
            print(f"[api_benchmark] Firebase init with projectId failed: {e}, trying default init...")
            firebase_admin.initialize_app()


async def run_benchmark(api_url: str):
    init_firebase()

    timestamp = int(time.time())
    test_email = f"test_api_{timestamp}@example.com"
    test_password = f"BenchP@ss{timestamp}!"
    firebase_uid = None
    id_token = None

    print(f"\n==================================================")
    print(f" DIRECT CLOUD RUN API BENCHMARK")
    print(f" API URL: {api_url}")
    print(f" User:    {test_email}")
    print(f"==================================================")

    try:
        # 1. Create verified test user programmatically
        print("[1/5] Creating verified test user in Firebase...")
        fb_user = fb_auth.create_user(
            email=test_email,
            password=test_password,
            email_verified=True,
            display_name="API Benchmark Tester",
        )
        firebase_uid = fb_user.uid
        print(f"       Created UID: {firebase_uid}")

        # 2. Exchange credentials for Firebase ID token via REST API
        print("[2/5] Minting Firebase ID token via Identity Toolkit...")
        sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={DEFAULT_FIREBASE_API_KEY}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth_res = await client.post(
                sign_in_url,
                json={"email": test_email, "password": test_password, "returnSecureToken": True},
            )
            auth_res.raise_for_status()
            id_token = auth_res.json()["idToken"]
            print("       Obtained valid Firebase ID token.")

        headers = {"Authorization": f"Bearer {id_token}"}

        # 3. Benchmark GET /health (5 sequential requests)
        print("[3/5] Benchmarking GET /health (5 sequential requests)...")
        health_latencies = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(5):
                t0 = time.perf_counter()
                res = await client.get(f"{api_url}/health")
                t1 = time.perf_counter()
                dur_ms = round((t1 - t0) * 1000)
                health_latencies.append(dur_ms)
                print(f"       Request {i+1}: {dur_ms} ms (Status: {res.status_code})")

        health_first_ms = health_latencies[0]
        health_warm_avg_ms = round(sum(health_latencies[1:]) / len(health_latencies[1:]))

        # 4. Benchmark GET /users/me (5 sequential requests)
        print("[4/5] Benchmarking GET /users/me (5 sequential requests)...")
        user_latencies = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(5):
                t0 = time.perf_counter()
                res = await client.get(f"{api_url}/users/me", headers=headers)
                t1 = time.perf_counter()
                dur_ms = round((t1 - t0) * 1000)
                user_latencies.append(dur_ms)
                print(f"       Request {i+1}: {dur_ms} ms (Status: {res.status_code})")

        users_me_first_ms = user_latencies[0]
        users_me_warm_avg_ms = round(sum(user_latencies[1:]) / len(user_latencies[1:]))

        # 5. Benchmark POST /query streaming
        print("[5/5] Benchmarking POST /query streaming...")
        session_id = str(uuid.uuid4())
        query_payload = {
            "session_id": session_id,
            "query": "What are the common medical reference ranges for healthy adults?",
            "language": "English",
        }

        query_ttft_ms = 0
        query_total_ms = 0
        first_chunk_received = False

        async with httpx.AsyncClient(timeout=90.0) as client:
            t0 = time.perf_counter()
            first_token_t = None
            async with client.stream("POST", f"{api_url}/query", json=query_payload, headers=headers) as stream_resp:
                if stream_resp.status_code != 200:
                    body = await stream_resp.aread()
                    raise RuntimeError(f"POST /query returned {stream_resp.status_code}: {body.decode()}")

                async for chunk in stream_resp.aiter_text():
                    if chunk.strip() and not first_chunk_received:
                        first_token_t = time.perf_counter()
                        first_chunk_received = True

            t1 = time.perf_counter()
            query_total_ms = round((t1 - t0) * 1000)
            if first_token_t:
                query_ttft_ms = round((first_token_t - t0) * 1000)
            else:
                query_ttft_ms = query_total_ms

        print(f"       TTFT: {query_ttft_ms} ms")
        print(f"       Total Stream: {query_total_ms} ms")

        # Format results strictly to requested specification
        section_text = (
            f"User: {test_email} (Direct Cloud Run API)\n"
            f"- GET /health (1st Hit):      {health_first_ms} ms\n"
            f"- GET /health (Warm Avg):     {health_warm_avg_ms} ms\n"
            f"- GET /users/me (1st Hit):    {users_me_first_ms} ms\n"
            f"- GET /users/me (Warm Avg):   {users_me_warm_avg_ms} ms\n"
            f"- POST /query (TTFT):         {query_ttft_ms} ms\n"
            f"- POST /query (Total Stream): {query_total_ms} ms"
        )

        append_to_testing_log(section_text)
        print("\nBenchmark results successfully logged.")
        print(section_text)

    finally:
        # Production cleanup
        print("\n[CLEANUP] Cleaning up benchmark test account from production...")
        if id_token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    del_res = await client.delete(
                        f"{api_url}/users/me",
                        headers={"Authorization": f"Bearer {id_token}"},
                    )
                    print(f"          DELETE /users/me status: {del_res.status_code}")
            except Exception as e:
                print(f"          Warning deleting Neon DB user: {e}")

        if firebase_uid:
            try:
                fb_auth.delete_user(firebase_uid)
                print(f"          Deleted Firebase UID: {firebase_uid}")
            except Exception as e:
                print(f"          Warning deleting Firebase user: {e}")


def main():
    parser = argparse.ArgumentParser(description="Direct Cloud Run API Benchmark")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Cloud Run backend URL")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.api_url))


if __name__ == "__main__":
    main()
