#!/usr/bin/env python3
"""
Micro-Benchmark for MediSkye Security Fixes:
1. DELETE /users/me/dependents/{dependent_id} cascade latency (< 500ms target).
2. POST /logout latency (< 100ms target).
3. Immediate GET /users/me 401 token-revocation rejection latency (< 10ms server target).

Runs N=10 warm measurements against live production:
https://mediskye-1095767703249.asia-southeast1.run.app
Appends results to ./testing_log.
"""

import asyncio
import datetime
import os
import sys
import time
import uuid
from typing import List, Dict, Tuple
import httpx
import firebase_admin
from firebase_admin import auth as fb_auth, credentials

# Ensure credentials env var is popped
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

DEFAULT_API_URL = "https://mediskye-1095767703249.asia-southeast1.run.app"
DEFAULT_FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


def calc_percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = f + 1
    if c < len(s):
        d0 = s[f] * (c - k)
        d1 = s[c] * (k - f)
        return round(d0 + d1, 1)
    return round(s[-1], 1)


def get_root_log_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current_dir, "..", "..", "testing_log"))


def append_to_testing_log(section_text: str):
    log_path = get_root_log_path()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + section_text + "\n")
    print(f"[micro_benchmark] Appended results to: {log_path}", flush=True)


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
                    return
                except Exception:
                    pass
        try:
            firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
        except Exception:
            firebase_admin.initialize_app()


async def mint_user_token(email: str, password: str) -> Tuple[str, str]:
    fb_user = fb_auth.create_user(
        email=email,
        password=password,
        email_verified=True,
        display_name="MicroBenchmark User",
    )
    sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={DEFAULT_FIREBASE_API_KEY}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(sign_in_url, json={"email": email, "password": password, "returnSecureToken": True})
        r.raise_for_status()
        return fb_user.uid, r.json()["idToken"]


async def run_micro_benchmarks(api_url: str = DEFAULT_API_URL, n_runs: int = 10):
    init_firebase()
    print("=" * 60)
    print("STARTING SECURITY FIXES MICRO-BENCHMARK (N=10)")
    print(f"Target: {api_url}")
    print("=" * 60)

    timestamp = int(time.time())
    master_email = f"micro_bench_{timestamp}@example.com"
    master_pass = f"MicroPass{timestamp}!"
    master_uid, master_token = await mint_user_token(master_email, master_pass)
    master_headers = {"Authorization": f"Bearer {master_token}"}

    dep_client_times: List[float] = []
    dep_server_times: List[float] = []

    logout_client_times: List[float] = []
    logout_server_times: List[float] = []

    revocation_401_client_times: List[float] = []
    revocation_401_server_times: List[float] = []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Initialize user in backend
            init_res = await client.get(f"{api_url}/users/me", headers=master_headers)
            print(f"[Init] Master user provisioned: {init_res.status_code}")

            # ---------------------------------------------------------
            # 1. Benchmark DELETE /users/me/dependents/{id} (N=10)
            # ---------------------------------------------------------
            print("\n[Bench 1] Measuring DELETE /users/me/dependents/{dependent_id}...")
            for i in range(n_runs):
                # Create a dependent profile
                dep_payload = {
                    "relationship": "Child",
                    "full_name": f"Child{i} Benchmark",
                    "date_of_birth": "2018-05-12",
                    "biological_sex": "Female",
                }
                c_res = await client.post(f"{api_url}/users/me/dependents", json=dep_payload, headers=master_headers)
                dep_id = c_res.json()["id"]

                # Measure DELETE
                t0 = time.perf_counter()
                d_res = await client.delete(f"{api_url}/users/me/dependents/{dep_id}", headers=master_headers)
                t1 = time.perf_counter()
                total_ms = (t1 - t0) * 1000.0
                srv_ms = float(d_res.headers.get("x-process-time-ms", "0"))

                dep_client_times.append(total_ms)
                dep_server_times.append(srv_ms)
                print(f"  Run {i+1:02d}: Client={total_ms:6.1f} ms | Server={srv_ms:5.1f} ms | Status={d_res.status_code}")
                await asyncio.sleep(0.1)

            # ---------------------------------------------------------
            # 2. Benchmark POST /logout and immediate GET /users/me 401 (N=10)
            # ---------------------------------------------------------
            print("\n[Bench 2] Measuring POST /logout & Immediate GET /users/me 401 Rejection...")
            for i in range(n_runs):
                sub_email = f"logout_run_{timestamp}_{i}@example.com"
                sub_uid, sub_token = await mint_user_token(sub_email, master_pass)
                sub_hdrs = {"Authorization": f"Bearer {sub_token}"}
                try:
                    # Provision user
                    await client.get(f"{api_url}/users/me", headers=sub_hdrs)

                    # POST /logout
                    t0 = time.perf_counter()
                    l_res = await client.post(f"{api_url}/logout", headers=sub_hdrs)
                    t1 = time.perf_counter()
                    logout_total_ms = (t1 - t0) * 1000.0
                    logout_srv_ms = float(l_res.headers.get("x-process-time-ms", "0"))
                    logout_client_times.append(logout_total_ms)
                    logout_server_times.append(logout_srv_ms)

                    # Immediate GET /users/me 401 rejection
                    t2 = time.perf_counter()
                    r_401 = await client.get(f"{api_url}/users/me", headers=sub_hdrs)
                    t3 = time.perf_counter()
                    rej_total_ms = (t3 - t2) * 1000.0
                    rej_srv_ms = float(r_401.headers.get("x-process-time-ms", "0"))
                    revocation_401_client_times.append(rej_total_ms)
                    revocation_401_server_times.append(rej_srv_ms)

                    print(
                        f"  Run {i+1:02d}: Logout Client={logout_total_ms:6.1f} ms (Server={logout_srv_ms:4.1f} ms) | "
                        f"401 Rejection Client={rej_total_ms:6.1f} ms (Server={rej_srv_ms:4.1f} ms, Code={r_401.status_code})"
                    )
                finally:
                    try:
                        fb_auth.delete_user(sub_uid)
                    except Exception:
                        pass
                await asyncio.sleep(0.1)

    finally:
        # Purge master user
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.delete(f"{api_url}/users/me", headers=master_headers)
        except Exception:
            pass
        try:
            fb_auth.delete_user(master_uid)
        except Exception:
            pass

    # Compile results
    dep_p50 = calc_percentile(dep_client_times, 50)
    dep_p95 = calc_percentile(dep_client_times, 95)
    dep_srv_p50 = calc_percentile(dep_server_times, 50)
    dep_srv_p95 = calc_percentile(dep_server_times, 95)

    logout_p50 = calc_percentile(logout_client_times, 50)
    logout_p95 = calc_percentile(logout_client_times, 95)
    logout_srv_p50 = calc_percentile(logout_server_times, 50)
    logout_srv_p95 = calc_percentile(logout_server_times, 95)

    rej_p50 = calc_percentile(revocation_401_client_times, 50)
    rej_p95 = calc_percentile(revocation_401_client_times, 95)
    rej_srv_p50 = calc_percentile(revocation_401_server_times, 50)
    rej_srv_p95 = calc_percentile(revocation_401_server_times, 95)

    report_lines = [
        "### Security Fixes Micro-Benchmark Results (N=10 Warm Runs)",
        "| Operation / Target | Warm Client p50 | Warm Client p95 | Server X-Process-Time (p50/p95) | Target Budget | Status |",
        "| :--- | ---: | ---: | ---: | :--- | :--- |",
        f"| `DELETE /users/me/dependents/{{id}}` Cascade | {dep_p50} ms | {dep_p95} ms | {dep_srv_p50} ms / {dep_srv_p95} ms | < 500 ms | {'PASS' if dep_p95 < 500 else 'FAIL'} |",
        f"| `POST /logout` Token Revocation | {logout_p50} ms | {logout_p95} ms | {logout_srv_p50} ms / {logout_srv_p95} ms | < 100 ms | {'PASS' if logout_p95 < 100 else 'FAIL'} |",
        f"| Immediate `GET /users/me` 401 Rejection | {rej_p50} ms | {rej_p95} ms | {rej_srv_p50} ms / {rej_srv_p95} ms | Server < 10 ms | {'PASS' if rej_srv_p95 < 10 else 'FAIL'} |",
    ]
    report_md = "\n".join(report_lines)
    print("\n" + report_md + "\n")
    append_to_testing_log(report_md)
    return {
        "dep_p50": dep_p50,
        "dep_p95": dep_p95,
        "dep_srv_p50": dep_srv_p50,
        "dep_srv_p95": dep_srv_p95,
        "logout_p50": logout_p50,
        "logout_p95": logout_p95,
        "logout_srv_p50": logout_srv_p50,
        "logout_srv_p95": logout_srv_p95,
        "rej_p50": rej_p50,
        "rej_p95": rej_p95,
        "rej_srv_p50": rej_srv_p50,
        "rej_srv_p95": rej_srv_p95,
    }


if __name__ == "__main__":
    asyncio.run(run_micro_benchmarks())
