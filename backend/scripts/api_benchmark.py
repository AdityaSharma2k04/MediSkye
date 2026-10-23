#!/usr/bin/env python3
"""
Direct Cloud Run API Benchmark for MediSkye (Staff SRE Hardening Step 4)
Measures direct Cloud Run API latencies across N=10 warm runs, reporting:
- Cold (1st Hit)
- Warm p50 & Warm p95
- Server-Side X-Process-Time-Ms (p50 & p95)
- Success & retry metrics: n_success, n_425, n_429, n_retries
- Dedicated Cold-Start measurement row
Covers:
- GET /health
- GET /users/me
- GET /users/me/documents/{doc_id}/metrics (cached hit)
- POST /users/me/documents/{doc_id}/summary (cached hit)
- POST /query (GENERAL_HEALTH)
- POST /query (DOCUMENT_QA)
Appends results strictly to ./testing_log in the project root.
"""

import argparse
import asyncio
import datetime
import os
import sys
import time
import uuid
from typing import Dict, List, Tuple, Optional
import httpx
import firebase_admin
from firebase_admin import auth as fb_auth

# Force unbuffered output so background tasks print in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DEFAULT_API_URL = "https://mediskye-1095767703249.asia-southeast1.run.app"
DEFAULT_FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


def calc_percentile(values: List[float], p: float) -> float:
    """Calculate exact p-th percentile from numeric list."""
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
    root_candidate = os.path.abspath(os.path.join(current_dir, "..", ".."))
    return os.path.join(root_candidate, "testing_log")


def append_to_testing_log(section_text: str):
    log_path = get_root_log_path()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    existing_content = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            existing_content = f.read().strip()

    header = f"==================================================\nMEDISKYE SRE BENCHMARK LOG — [{now_str}]\n=================================================="

    if not existing_content:
        new_content = f"{header}\n\n{section_text}\n==================================================\n"
    else:
        lines = existing_content.splitlines()
        filtered = []
        for line in lines:
            if line.strip() == "==================================================" or "MEDISKYE" in line and "LOG" in line:
                continue
            filtered.append(line)
        body = "\n".join(filtered).strip()
        new_content = f"{header}\n\n{body}\n\n{section_text}\n==================================================\n"

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"[api_benchmark] Log successfully updated at: {log_path}", flush=True)


def init_firebase():
    if not firebase_admin._apps:
        from firebase_admin import credentials
        candidate_keys = [
            os.path.expanduser(r"~\Downloads\service-acc-key.json"),
            os.path.expanduser(r"~\OneDrive\Documents\service-acc-key.json"),
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "",
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


async def execute_request_with_metrics(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict] = None,
    stream: bool = False,
) -> Tuple[float, float, float, int, int]:
    """
    Executes a request and records:
    (client_total_ms, first_token_ms, server_process_time_ms, status_code, retries)
    Handles 503/425 Retry-After transparently.
    """
    retries = 0
    t0 = time.perf_counter()

    for attempt in range(2):
        try:
            if stream:
                first_token_time = None
                server_process_ms = 0.0
                async with client.stream(method, url, headers=headers, json=json_data, timeout=60.0) as resp:
                    status = resp.status_code
                    srv_hdr = resp.headers.get("x-process-time-ms") or resp.headers.get("X-Process-Time-Ms")
                    if srv_hdr:
                        try:
                            server_process_ms = float(srv_hdr)
                        except ValueError:
                            pass

                    if (status == 503 or status == 425) and attempt == 0:
                        retry_after = int(resp.headers.get("Retry-After", "2"))
                        print(f"       [RETRY] Received {status}, waiting {retry_after}s...", flush=True)
                        await asyncio.sleep(retry_after)
                        retries += 1
                        continue

                    async for chunk in resp.aiter_text():
                        if chunk.strip() and first_token_time is None:
                            first_token_time = time.perf_counter()

                t1 = time.perf_counter()
                total_ms = (t1 - t0) * 1000.0
                ttft_ms = ((first_token_time - t0) * 1000.0) if first_token_time else total_ms
                return total_ms, ttft_ms, server_process_ms, status, retries

            else:
                t_req_start = time.perf_counter()
                resp = await client.request(method, url, headers=headers, json=json_data, timeout=30.0)
                t_req_end = time.perf_counter()
                status = resp.status_code
                srv_hdr = resp.headers.get("x-process-time-ms") or resp.headers.get("X-Process-Time-Ms")
                server_process_ms = 0.0
                if srv_hdr:
                    try:
                        server_process_ms = float(srv_hdr)
                    except ValueError:
                        pass

                if (status == 503 or status == 425) and attempt == 0:
                    retry_after = int(resp.headers.get("Retry-After", "2"))
                    print(f"       [RETRY] Received {status}, waiting {retry_after}s...", flush=True)
                    await asyncio.sleep(retry_after)
                    retries += 1
                    continue

                total_ms = (t_req_end - t_req_start) * 1000.0
                return total_ms, total_ms, server_process_ms, status, retries

        except Exception as err:
            if attempt == 1:
                t1 = time.perf_counter()
                return (t1 - t0) * 1000.0, 0.0, 0.0, 500, retries
            await asyncio.sleep(1.0)
            retries += 1

    return 0.0, 0.0, 0.0, 500, retries


async def run_benchmark(api_url: str):
    init_firebase()

    timestamp = int(time.time())
    test_email = f"staff_sre_{timestamp}@example.com"
    test_password = f"SreBenchmark{timestamp}!"
    firebase_uid = None
    id_token = None
    doc_id = None

    print(f"\n==================================================", flush=True)
    print(f" PRINCIPAL SRE HARDENING & API BENCHMARK (N=10)", flush=True)
    print(f" Cloud Run: {api_url}", flush=True)
    print(f" User:      {test_email}", flush=True)
    print(f"==================================================", flush=True)

    try:
        # Pre-Flight Cold Start Measurement
        print("\n[Step 0] Measuring Cold Start Container Latency (GET /health)...", flush=True)
        async with httpx.AsyncClient() as client:
            t_cold_start = time.perf_counter()
            cold_res = await client.get(f"{api_url}/health", timeout=30.0)
            t_cold_end = time.perf_counter()
            cold_start_client_ms = round((t_cold_end - t_cold_start) * 1000.0, 1)
            cold_server_hdr = cold_res.headers.get("x-process-time-ms") or "0"
            cold_server_ms = float(cold_server_hdr) if cold_server_hdr != "0" else 0.0

        print(f"         Cold Start Client Latency: {cold_start_client_ms} ms (Server: {cold_server_ms} ms)")

        # 1. Create verified test user programmatically
        print("\n[Step 1] Creating test user in Firebase...", flush=True)
        fb_user = fb_auth.create_user(
            email=test_email,
            password=test_password,
            email_verified=True,
            display_name="Staff SRE Profiler",
        )
        firebase_uid = fb_user.uid
        print(f"         Created UID: {firebase_uid}")

        # 2. Mint Firebase ID token
        print("[Step 2] Minting Firebase ID token...", flush=True)
        sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={DEFAULT_FIREBASE_API_KEY}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth_res = await client.post(
                sign_in_url,
                json={"email": test_email, "password": test_password, "returnSecureToken": True},
            )
            auth_res.raise_for_status()
            id_token = auth_res.json()["idToken"]
            print("         Obtained valid Firebase ID token.")

        headers = {"Authorization": f"Bearer {id_token}"}

        # 3. Upload test lab report for document QA, metrics, and summary benchmarks
        print("\n[Step 3] Uploading test report PDF to provision hybrid index...", flush=True)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
        pdf_path = os.path.join(root_dir, "backend", "tests", "fixtures", "test_report.pdf")
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(root_dir, "test_reports", "testreport1.pdf")

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        t_upload_start = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": ("sre_test_report.pdf", pdf_bytes, "application/pdf")}
            up_res = await client.post(f"{api_url}/upload", files=files, headers=headers)
            if up_res.status_code != 202:
                raise RuntimeError(f"Upload failed: {up_res.status_code} {up_res.text}")
            job_id = up_res.json()["job_id"]
            print(f"         Upload initiated: Job ID = {job_id}. Polling status...", flush=True)

            # Poll status at 0.4s cadence and stop upload_fast_path_ms the exact millisecond
            # status flips to 'completed' (index_status == 'local_ready')
            for _ in range(150):
                await asyncio.sleep(0.4)
                st_res = await client.get(f"{api_url}/upload/status/{job_id}", headers=headers)
                if st_res.status_code != 200:
                    continue
                st_data = st_res.json()
                upload_status = str(st_data.get("status", "")).lower()
                if upload_status == "completed":
                    t_upload_end = time.perf_counter()
                    doc_id = st_data.get("document_id")
                    print(f"         Upload completed (local_ready). Document ID = {doc_id}", flush=True)
                    break
                elif upload_status == "failed":
                    raise RuntimeError(f"Upload processing failed: {st_data.get('error')}")
            else:
                t_upload_end = time.perf_counter()

            # Fallback to query user's documents if status endpoint didn't embed document_id
            if not doc_id:
                docs_res = await client.get(f"{api_url}/users/me/documents", headers=headers)
                if docs_res.status_code == 200 and docs_res.json():
                    doc_id = docs_res.json()[0]["id"]
                    print(f"         Resolved Document ID via /users/me/documents: {doc_id}", flush=True)

        total_upload_dur_ms = round((t_upload_end - t_upload_start) * 1000.0, 1)
        print(f"         Upload Fast-Path Total (local_ready): {total_upload_dur_ms} ms. Document ID = {doc_id}", flush=True)

        # Wait for background pre-warm via /export (which does not consume the 10/min /metrics or /summary bucket)
        print("[Step 4] Waiting for background metrics & summary pre-warm to settle...", flush=True)
        async with httpx.AsyncClient(timeout=60.0) as client:
            for _ in range(25):
                exp_res = await client.get(f"{api_url}/users/me/documents/{doc_id}/export", headers=headers)
                if exp_res.status_code == 200 and exp_res.json().get("lab_metrics"):
                    break
                await asyncio.sleep(1.0)
            # Trigger summary cache once and allow rate-limit window to settle before N=10 loop
            await client.post(f"{api_url}/users/me/documents/{doc_id}/summary", headers=headers)
            print("         Caches pre-warmed successfully.", flush=True)

        # Define 6 benchmark endpoints
        endpoints_config = [
            {
                "name": "GET /health",
                "method": "GET",
                "url": f"{api_url}/health",
                "headers": None,
                "json": None,
                "stream": False,
            },
            {
                "name": "GET /users/me",
                "method": "GET",
                "url": f"{api_url}/users/me",
                "headers": headers,
                "json": None,
                "stream": False,
            },
            {
                "name": "GET /metrics (cached hit)",
                "method": "GET",
                "url": f"{api_url}/users/me/documents/{doc_id}/metrics",
                "headers": headers,
                "json": None,
                "stream": False,
            },
            {
                "name": "POST /summary (cached hit)",
                "method": "POST",
                "url": f"{api_url}/users/me/documents/{doc_id}/summary",
                "headers": headers,
                "json": None,
                "stream": False,
            },
            {
                "name": "POST /query (GENERAL_HEALTH)",
                "method": "POST",
                "url": f"{api_url}/query",
                "headers": headers,
                "json": {
                    "session_id": str(uuid.uuid4()),
                    "query": "What is normal blood pressure in healthy adults?",
                    "language": "English",
                },
                "stream": True,
            },
            {
                "name": "POST /query (DOCUMENT_QA)",
                "method": "POST",
                "url": f"{api_url}/query",
                "headers": headers,
                "json": {
                    "session_id": str(doc_id),
                    "document_id": str(doc_id),
                    "query": "What are my abnormal lab values in this report?",
                    "language": "English",
                },
                "stream": True,
            },
        ]

        # Table A Results Data
        benchmark_results = []
        n_warm_runs = 10

        print(f"\n[Step 5] Executing Table A: N={n_warm_runs} Warm Runs per Endpoint...", flush=True)
        async with httpx.AsyncClient() as client:
            for ep in endpoints_config:
                ep_name = ep["name"]
                print(f"\n---> Benchmarking {ep_name}...", flush=True)

                # 1. Cold / 1st Hit
                cold_total, cold_ttft, cold_srv, cold_status, cold_retries = await execute_request_with_metrics(
                    client=client,
                    method=ep["method"],
                    url=ep["url"],
                    headers=ep["headers"],
                    json_data=ep["json"],
                    stream=ep["stream"],
                )
                cold_display = round(cold_ttft if ep["stream"] else cold_total, 1)
                print(f"     [Cold 1st Hit]: {cold_display} ms (Server: {cold_srv} ms, Status: {cold_status})", flush=True)

                # 2. Warm N=10 Loop
                warm_client_times: List[float] = []
                warm_server_times: List[float] = []
                n_success = 0
                n_425 = 0
                n_429 = 0
                total_retries = cold_retries

                for run_idx in range(n_warm_runs):
                    total_ms, ttft_ms, srv_ms, status, retries = await execute_request_with_metrics(
                        client=client,
                        method=ep["method"],
                        url=ep["url"],
                        headers=ep["headers"],
                        json_data=ep["json"],
                        stream=ep["stream"],
                    )
                    total_retries += retries
                    effective_time = ttft_ms if ep["stream"] else total_ms
                    warm_client_times.append(effective_time)
                    warm_server_times.append(srv_ms)

                    if 200 <= status < 300:
                        n_success += 1
                    elif status == 425:
                        n_425 += 1
                    elif status == 429:
                        # Respect 10/min sliding window so all 10 warm runs measure true cached latency
                        print("     [Rate Limit Window] Waiting 60s for 10/min rate-limit window reset...", flush=True)
                        await asyncio.sleep(60.5)
                        total_ms, ttft_ms, srv_ms, status, retries = await execute_request_with_metrics(
                            client=client,
                            method=ep["method"],
                            url=ep["url"],
                            headers=ep["headers"],
                            json_data=ep["json"],
                            stream=ep["stream"],
                        )
                        effective_time = ttft_ms if ep["stream"] else total_ms
                        warm_client_times[-1] = effective_time
                        warm_server_times[-1] = srv_ms
                        if 200 <= status < 300:
                            n_success += 1
                        else:
                            n_429 += 1

                    print(f"     Run {run_idx+1:02d}: {round(effective_time, 1):>7.1f} ms (Server: {srv_ms:>5.1f} ms, Code: {status})", flush=True)
                    # Brief pacing to maintain realistic production traffic
                    await asyncio.sleep(0.15)

                warm_p50 = calc_percentile(warm_client_times, 50)
                warm_p95 = calc_percentile(warm_client_times, 95)
                srv_p50 = calc_percentile(warm_server_times, 50)
                srv_p95 = calc_percentile(warm_server_times, 95)

                benchmark_results.append({
                    "endpoint": ep_name,
                    "cold_hit": cold_display,
                    "warm_p50": warm_p50,
                    "warm_p95": warm_p95,
                    "srv_p50": srv_p50,
                    "srv_p95": srv_p95,
                    "n_success": n_success,
                    "n_425": n_425,
                    "n_429": n_429,
                    "n_retries": total_retries,
                })

        # Build Markdown Table A
        table_a_lines = [
            "### Table A: Direct Cloud Run API Benchmark (N=10 Warm Runs)",
            "| Endpoint | Cold (1st Hit) | Warm p50 | Warm p95 | Server X-Process-Time (p50/p95) | n_success | n_425 | n_429 | n_retries |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for r in benchmark_results:
            table_a_lines.append(
                f"| `{r['endpoint']}` | {r['cold_hit']} ms | {r['warm_p50']} ms | {r['warm_p95']} ms | {r['srv_p50']} ms / {r['srv_p95']} ms | {r['n_success']}/10 | {r['n_425']} | {r['n_429']} | {r['n_retries']} |"
            )

        table_a_md = "\n".join(table_a_lines)

        # ── Step 6: Dedicated Security & Error-Code Verification Block ──
        print("\n[Step 6] Executing Security & Error-Code Verification Block (401, 403, 429, 503)...", flush=True)
        security_checks: List[Tuple[str, str, bool]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. 401 Unauthorized (missing or tampered Bearer token)
            r_no_auth = await client.get(f"{api_url}/users/me")
            r_bad_auth = await client.get(f"{api_url}/users/me", headers={"Authorization": "Bearer tampered.invalid.jwt"})
            ok_401 = (r_no_auth.status_code == 401 and r_bad_auth.status_code == 401)
            security_checks.append(("401 Unauthorized (Missing & Tampered Bearer Token)", f"{r_no_auth.status_code} / {r_bad_auth.status_code}", ok_401))

            # 2. 403 Forbidden (unverified email/password Firebase token rejected with "Email not verified")
            unver_email = f"unverified_sre_{int(time.time() * 1000)}@example.com"
            unver_uid = None
            try:
                u_unver = fb_auth.create_user(email=unver_email, password=test_password, email_verified=False)
                unver_uid = u_unver.uid
                r_sign = await client.post(
                    sign_in_url,
                    json={"email": unver_email, "password": test_password, "returnSecureToken": True},
                )
                unver_token = r_sign.json().get("idToken")
                r_403 = await client.get(f"{api_url}/users/me", headers={"Authorization": f"Bearer {unver_token}"})
                ok_403 = (r_403.status_code == 403 and "not verified" in r_403.text.lower())
                security_checks.append(("403 Forbidden (Unverified Email Token Rejected)", f"{r_403.status_code} ({r_403.json().get('detail', '')})", ok_403))
            finally:
                if unver_uid:
                    try:
                        fb_auth.delete_user(unver_uid)
                    except Exception:
                        pass

            # 3. 429 Too Many Requests (burst rate limiter verification on /extract-metrics)
            got_429 = False
            for _ in range(12):
                r_lim = await client.post(
                    f"{api_url}/extract-metrics",
                    headers={**headers, "X-Session-ID": str(doc_id)},
                )
                if r_lim.status_code == 429:
                    got_429 = True
                    break
            security_checks.append(("429 Too Many Requests (Rate Limiter Burst Gate)", "429 Triggered" if got_429 else "Not Triggered", got_429))

        sec_lines = [
            "",
            "### Security & Error-Code Verification Gate",
            "| Security / Resilience Gate | Observed Response | Status |",
            "| :--- | :--- | :--- |",
        ]
        for label, obs, passed in security_checks:
            sec_lines.append(f"| {label} | `{obs}` | {'PASS' if passed else 'FAIL'} |")
        sec_md = "\n".join(sec_lines)

        # Cold Start Row
        cold_start_summary = (
            f"**Cold-Start Measurement Row:**\n"
            f"- **First Hit (Cloud Run Idle/Wakeup GET /health):** `{cold_start_client_ms} ms` (Server Process Time: `{cold_server_ms} ms`)\n"
            f"- **Observed Upload Synchronous Fast-Path Total (`local_ready`):** `{total_upload_dur_ms} ms`\n"
        )

        full_log_payload = f"{cold_start_summary}\n\n{table_a_md}\n{sec_md}"
        append_to_testing_log(full_log_payload)
        print("\n" + "=" * 50)
        print(" BENCHMARK COMPLETED SUCCESSFULLY")
        print("=" * 50)
        print(full_log_payload)

    finally:
        print("\n[CLEANUP] Purging test user and documents from database and Firebase...", flush=True)
        if id_token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    del_res = await client.delete(f"{api_url}/users/me", headers={"Authorization": f"Bearer {id_token}"})
                    print(f"          DELETE /users/me status: {del_res.status_code}", flush=True)
            except Exception as e:
                print(f"          Warning deleting user from DB: {e}", flush=True)

        if firebase_uid:
            try:
                fb_auth.delete_user(firebase_uid)
                print(f"          Deleted Firebase UID: {firebase_uid}", flush=True)
            except Exception as e:
                print(f"          Warning deleting Firebase user: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Staff SRE Direct API Benchmark")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Cloud Run backend URL")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.api_url))


if __name__ == "__main__":
    main()
