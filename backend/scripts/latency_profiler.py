#!/usr/bin/env python3
"""
Real-World E2E Browser Latency Profiler for MediSkye
Uses Playwright to profile live Cloudflare Pages frontend + Cloud Run backend.
Measures millisecond latencies for Page Load, Auth Login, PDF Upload,
Lab Metrics (1st & cached), Summary (1st & cached), and AI Chat (TTFT & stream).
Logs results strictly to ./testing_log in the project root.
"""

import argparse
import asyncio
import datetime
import os
import sys
import time
import httpx
import firebase_admin
from firebase_admin import auth as fb_auth
from playwright.async_api import async_playwright

# Force unbuffered output so background tasks print in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DEFAULT_FRONTEND_URL = "https://mediskye.pages.dev"
DEFAULT_API_URL = "https://mediskye-1095767703249.asia-southeast1.run.app"
DEFAULT_FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


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

    header = f"==================================================\nMEDISKYE LATENCY LOG — [{now_str}]\n=================================================="

    if not existing_content:
        new_content = f"{header}\n\n{section_text}\n==================================================\n"
    else:
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
    print(f"[latency_profiler] Log updated at: {log_path}", flush=True)


def init_firebase():
    if not firebase_admin._apps:
        try:
            firebase_admin.initialize_app(options={"projectId": PROJECT_ID})
        except Exception:
            firebase_admin.initialize_app()


async def run_profiler(frontend_url: str, api_url: str, headless: bool = True):
    init_firebase()

    timestamp = int(time.time())
    test_email = f"test_e2e_{timestamp}@example.com"
    test_password = f"E2eP@ss{timestamp}!"
    firebase_uid = None
    bearer_token = None

    # Resolve PDF fixture
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
    pdf_fixture = os.path.join(root_dir, "backend", "tests", "fixtures", "test_report.pdf")
    if not os.path.exists(pdf_fixture):
        alt_fixture = os.path.join(root_dir, "test_reports", "testreport1.pdf")
        if os.path.exists(alt_fixture):
            pdf_fixture = alt_fixture
        else:
            raise FileNotFoundError(f"Cannot find PDF report fixture at {pdf_fixture}")

    print(f"\n==================================================", flush=True)
    print(f" REAL-WORLD E2E BROWSER LATENCY PROFILER", flush=True)
    print(f" Frontend: {frontend_url}", flush=True)
    print(f" CloudRun: {api_url}", flush=True)
    print(f" Fixture:  {pdf_fixture}", flush=True)
    print(f" User:     {test_email}", flush=True)
    print(f" Headless: {headless}", flush=True)
    print(f"==================================================", flush=True)

    # Waterfall timing tracker
    network_timings = {}
    request_start_times = {}

    def on_request(req):
        request_start_times[req] = time.perf_counter()

    def on_response(res):
        req = res.request
        if req in request_start_times:
            duration_ms = round((time.perf_counter() - request_start_times[req]) * 1000)
            url = req.url
            for ep in ["/upload/status", "/upload", "/extract-metrics", "/metrics", "/summary", "/query", "/users/me", "/health"]:
                if ep in url:
                    clean_ep = ep
                    if "metrics" in ep:
                        clean_ep = "/metrics"
                    if clean_ep not in network_timings:
                        network_timings[clean_ep] = []
                    network_timings[clean_ep].append(duration_ms)
                    break

    try:
        # 1. Programmatically create verified Firebase user
        print("\n[1/7] Creating verified test user in Firebase...", flush=True)
        fb_user = None
        for attempt in range(3):
            try:
                fb_user = fb_auth.create_user(
                    email=test_email,
                    password=test_password,
                    email_verified=True,
                    display_name="E2E Profiler Tester",
                )
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"       User creation transient error ({e}), retrying in 2s...", flush=True)
                await asyncio.sleep(2.0)

        firebase_uid = fb_user.uid
        print(f"       Created UID: {firebase_uid}", flush=True)

        # Pre-fetch ID token for backup cleanup
        sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={DEFAULT_FIREBASE_API_KEY}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            auth_res = await client.post(
                sign_in_url,
                json={"email": test_email, "password": test_password, "returnSecureToken": True},
            )
            if auth_res.status_code == 200:
                bearer_token = auth_res.json().get("idToken")

        # 2. Launch Playwright Chromium
        print("\n[2/7] Launching Playwright browser...", flush=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Mock window.print so printing doesn't block headless execution
            await page.add_init_script("""
                window.__print_called__ = 0;
                window.print = () => {
                    window.__print_called__ += 1;
                    console.log('[E2E] window.print() triggered, count=' + window.__print_called__);
                    setTimeout(() => window.dispatchEvent(new Event('afterprint')), 50);
                };
            """)

            # Attach network waterfall listener
            page.on("request", on_request)
            page.on("response", on_response)

            # Glitch & error listener
            async def handle_page_error(err):
                ts = int(time.time())
                err_path = os.path.join(current_dir, f"error_{ts}.png")
                print(f"[E2E ERROR] Page error: {err}", flush=True)
                try:
                    await page.screenshot(path=err_path)
                    print(f"            Saved screenshot to: {err_path}", flush=True)
                except Exception:
                    pass

            page.on("pageerror", lambda e: asyncio.create_task(handle_page_error(e)))

            # Measure Page Load Latency
            print("\n[3/7] Measuring Cold Page Load Latency...", flush=True)
            t_load_start = time.perf_counter()
            await page.goto(f"{frontend_url}/login", wait_until="networkidle")
            await page.wait_for_selector("#login-email", state="visible", timeout=30000)
            t_load_end = time.perf_counter()
            page_load_ms = round((t_load_end - t_load_start) * 1000)
            print(f"       Page Load: {page_load_ms} ms", flush=True)

            # Measure Login & Auth Redirect Latency
            print("\n[4/7] Measuring Login & Auth Redirect Latency...", flush=True)
            await page.fill("#login-email", test_email)
            await page.click("button[type='submit']")
            await page.wait_for_selector("#login-password", state="visible", timeout=15000)
            await page.fill("#login-password", test_password)

            t_login_start = time.perf_counter()
            await page.click("button[type='submit']")

            # Wait until client-side routing completes to /chat and chat interface is rendered
            await page.wait_for_function("() => window.location.pathname.includes('/chat')", timeout=30000)
            await page.wait_for_selector("textarea", state="visible", timeout=30000)
            t_login_end = time.perf_counter()
            auth_login_ms = round((t_login_end - t_login_start) * 1000)
            print(f"       Login & Auth Redirect: {auth_login_ms} ms", flush=True)

            # Retrieve browser token if available
            stored_token = await page.evaluate("() => localStorage.getItem('token')")
            if stored_token:
                bearer_token = stored_token

            # Dismiss Memory Consent modal if present on initial login
            try:
                consent_btn = await page.wait_for_selector('button:has-text("Allow"), button:has-text("Skip")', timeout=3000)
                if consent_btn:
                    await consent_btn.click()
                    print("       Dismissed initial Memory Consent modal.", flush=True)
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Measure PDF Upload & Processing Latency
            print("\n[5/7] Uploading PDF Report & Measuring Processing Latency...", flush=True)
            await page.wait_for_selector("input[type='file']", state="attached", timeout=15000)

            t_upload_start = time.perf_counter()
            await page.set_input_files("input[type='file']", pdf_fixture)

            # Wait for "Report Ready" toast or lab metrics button indicating processing is complete
            metrics_btn_selector = 'button[aria-label="View extracted lab metrics table"]'
            await page.wait_for_selector('text="Report Ready"', state="visible", timeout=120000)
            await page.wait_for_selector(metrics_btn_selector, state="visible", timeout=15000)
            t_upload_end = time.perf_counter()
            pdf_upload_total_ms = round((t_upload_end - t_upload_start) * 1000)
            print(f"       PDF Upload & Processing: {pdf_upload_total_ms} ms", flush=True)

            # Measure Lab Metrics Load (1st Run vs Cached)
            print("\n[6/7] Measuring Lab Metrics Load Latency...", flush=True)
            # First load
            t_metrics_1_start = time.perf_counter()
            async with page.expect_response(lambda res: ("extract-metrics" in res.url or "metrics" in res.url) and res.status == 200, timeout=60000):
                await page.click(metrics_btn_selector)
            await page.wait_for_selector("text=Clinical Lab Metrics", state="visible", timeout=30000)
            t_metrics_1_end = time.perf_counter()
            metrics_first_load_ms = round((t_metrics_1_end - t_metrics_1_start) * 1000)
            print(f"       Lab Metrics (1st Run): {metrics_first_load_ms} ms", flush=True)

            # Switch back to Chat view
            chat_btn_selector = 'button[aria-label="Switch to chat view"]'
            await page.click(chat_btn_selector)
            await page.wait_for_selector("textarea", state="visible", timeout=15000)

            # Second load (Cached)
            t_metrics_2_start = time.perf_counter()
            async with page.expect_response(lambda res: ("extract-metrics" in res.url or "metrics" in res.url) and res.status == 200, timeout=30000):
                await page.click(metrics_btn_selector)
            await page.wait_for_selector("text=Clinical Lab Metrics", state="visible", timeout=30000)
            t_metrics_2_end = time.perf_counter()
            metrics_cached_load_ms = round((t_metrics_2_end - t_metrics_2_start) * 1000)
            print(f"       Lab Metrics (Cached): {metrics_cached_load_ms} ms", flush=True)

            # Switch back to Chat view
            await page.click(chat_btn_selector)
            await page.wait_for_selector("textarea", state="visible", timeout=15000)

            # Measure Print Summary Generation (1st Run vs Cached)
            print("\n[7/7] Measuring Print Summary Generation Latency...", flush=True)
            summary_btn_selector = 'button[aria-label="Export Summary"]'
            t_summary_1_start = time.perf_counter()
            async with page.expect_response(lambda res: "/summary" in res.url and res.status == 200, timeout=60000):
                await page.click(summary_btn_selector)
            await page.wait_for_function("() => window.__print_called__ >= 1", timeout=10000)
            t_summary_1_end = time.perf_counter()
            summary_first_ms = round((t_summary_1_end - t_summary_1_start) * 1000)
            print(f"       Print Summary (1st Run): {summary_first_ms} ms", flush=True)

            # Brief pause for state transition
            await asyncio.sleep(1.0)

            # Second load (Cached Summary)
            t_summary_2_start = time.perf_counter()
            async with page.expect_response(lambda res: "/summary" in res.url and res.status == 200, timeout=30000):
                await page.click(summary_btn_selector)
            await page.wait_for_function("() => window.__print_called__ >= 2", timeout=10000)
            t_summary_2_end = time.perf_counter()
            summary_cached_ms = round((t_summary_2_end - t_summary_2_start) * 1000)
            print(f"       Print Summary (Cached): {summary_cached_ms} ms", flush=True)

            # Measure AI Chat Query (TTFT & Total Stream)
            print("\n[8/7] Measuring AI Chat Query Latency...", flush=True)
            chat_input = await page.wait_for_selector("textarea", state="visible", timeout=15000)
            await chat_input.fill("What are my abnormal values?")

            send_btn_selector = 'button[aria-label="Send message"]'
            send_btn = await page.wait_for_selector(send_btn_selector, state="visible", timeout=15000)

            init_prose_count = await page.locator(".chat-messages-container .prose").count()
            t_chat_start = time.perf_counter()
            await send_btn.click()

            # TTFT: Wait for assistant prose block to appear and receive content
            t_ttft = None
            deadline = time.perf_counter() + 60.0
            while time.perf_counter() < deadline:
                current_prose_count = await page.locator(".chat-messages-container .prose").count()
                if current_prose_count > init_prose_count:
                    t_ttft = time.perf_counter()
                    break
                await asyncio.sleep(0.05)

            if t_ttft is None:
                t_ttft = time.perf_counter()

            ai_ttft_ms = round((t_ttft - t_chat_start) * 1000)
            print(f"       AI Chat TTFT (1st Token): {ai_ttft_ms} ms", flush=True)

            # Total stream: Wait until response action bar appears (Copy response button)
            await page.wait_for_selector('button[aria-label="Copy response"]', state="visible", timeout=120000)
            t_stream_end = time.perf_counter()
            ai_total_stream_ms = round((t_stream_end - t_chat_start) * 1000)
            print(f"       AI Chat Total Stream: {ai_total_stream_ms} ms", flush=True)

            await browser.close()

        # Format and save strictly to requested specification
        section_text = (
            f"User: {test_email} (Browser E2E Flow)\n"
            f"- Page Load:                  {page_load_ms} ms\n"
            f"- Login & Auth Redirect:      {auth_login_ms} ms\n"
            f"- PDF Upload & Processing:    {pdf_upload_total_ms} ms\n"
            f"- Lab Metrics (1st Run):      {metrics_first_load_ms} ms\n"
            f"- Lab Metrics (Cached):       {metrics_cached_load_ms} ms\n"
            f"- Print Summary (1st Run):    {summary_first_ms} ms\n"
            f"- Print Summary (Cached):     {summary_cached_ms} ms\n"
            f"- AI Chat TTFT (1st Token):   {ai_ttft_ms} ms\n"
            f"- AI Chat Total Stream:       {ai_total_stream_ms} ms"
        )

        append_to_testing_log(section_text)
        print("\nE2E Profiling successfully logged to ./testing_log.", flush=True)
        print(section_text, flush=True)

        # Print network waterfall summary
        print("\n--- Network Waterfall Breakdown ---", flush=True)
        for ep, timings in network_timings.items():
            avg_time = round(sum(timings) / len(timings)) if timings else 0
            print(f"  {ep:<20} Hits: {len(timings):<3} Avg: {avg_time:<5} ms  (Raw: {timings})", flush=True)

        return {
            "page_load_ms": page_load_ms,
            "auth_login_ms": auth_login_ms,
            "pdf_upload_total_ms": pdf_upload_total_ms,
            "metrics_first_load_ms": metrics_first_load_ms,
            "metrics_cached_load_ms": metrics_cached_load_ms,
            "summary_first_ms": summary_first_ms,
            "summary_cached_ms": summary_cached_ms,
            "ai_ttft_ms": ai_ttft_ms,
            "ai_total_stream_ms": ai_total_stream_ms,
            "network_timings": network_timings,
        }

    finally:
        # Production cleanup
        print("\n[CLEANUP] Cleaning up E2E test account and documents from production...", flush=True)
        if bearer_token:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    del_res = await client.delete(
                        f"{api_url}/users/me",
                        headers={"Authorization": f"Bearer {bearer_token}"},
                    )
                    print(f"          DELETE /users/me status: {del_res.status_code}", flush=True)
            except Exception as e:
                print(f"          Warning deleting Neon DB user: {e}", flush=True)

        if firebase_uid:
            try:
                fb_auth.delete_user(firebase_uid)
                print(f"          Deleted Firebase UID: {firebase_uid}", flush=True)
            except Exception as e:
                print(f"          Warning deleting Firebase user: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Real-World E2E Browser Latency Profiler")
    parser.add_argument("--url", default=DEFAULT_FRONTEND_URL, help="Frontend live URL")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Cloud Run backend URL")
    parser.add_argument("--no-headless", action="store_true", help="Run browser in headful mode")
    args = parser.parse_args()

    asyncio.run(run_profiler(args.url, args.api_url, headless=not args.no_headless))


if __name__ == "__main__":
    main()
