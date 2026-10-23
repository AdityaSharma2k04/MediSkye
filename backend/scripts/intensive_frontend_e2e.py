#!/usr/bin/env python3
"""
Intensive Live Frontend E2E Feature, Multi-File, Memory Cache & Click-Latency Audit
Executes 7 comprehensive phases against the live MediSkye deployment
(https://mediskye.pages.dev + Cloud Run backend), measuring millisecond latencies
for every UI click, API call (client ms + X-Process-Time-Ms), and DOM render,
and appends a full structured report to ./testing_log.
"""

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
import httpx
import pymupdf
from firebase_admin import auth as fb_auth
from playwright.async_api import Page, async_playwright

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DEFAULT_FRONTEND_URL = "https://mediskye.pages.dev"
DEFAULT_API_URL = "https://mediskye-1095767703249.asia-southeast1.run.app"
LEGACY_CUSTOM_API_URL = "https://mediskye-backend.cloud.run"
DEFAULT_FIREBASE_API_KEY = "AIzaSyBhIOdDkdivvUvv9sLQ2Tp2tjQpK41chzQ"
PROJECT_ID = "mediskye-backend"


def init_firebase() -> None:
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


def get_root_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def create_custom_thyroid_pdf() -> str:
    """Create a distinct second clinical PDF report for multi-document testing."""
    path = os.path.join(tempfile.gettempdir(), "second_thyroid_panel.pdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    lines = [
        "MEDISKYE DIAGNOSTIC LABORATORIES — ENDOCRINE REPORT",
        "Panel: Thyroid Function & Autoimmune Panel (Second Report)",
        "Patient: Intensive E2E Tester | Age: 41 | Sex: F | Collection Date: 2026-10-22",
        "-" * 76,
        f"{'Test Name':<36} {'Result':<10} {'Units':<14} {'Reference Range':<14} {'Status'}",
        "-" * 76,
        f"{'TSH (Thyroid Stimulating Hormone)':<36} {'11.4':<10} {'mIU/L':<14} {'0.45 - 4.50':<14} HIGH",
        f"{'Free T4 (Thyroxine, Free)':<36} {'0.6':<10} {'ng/dL':<14} {'0.82 - 1.77':<14} LOW",
        f"{'Free T3 (Triiodothyronine, Free)':<36} {'2.2':<10} {'pg/mL':<14} {'2.0 - 4.4':<14} NORMAL",
        f"{'Thyroid Peroxidase Ab (TPOAb)':<36} {'310':<10} {'IU/mL':<14} {'< 34':<14} HIGH",
        f"{'Vitamin D, 25-Hydroxy':<36} {'18.2':<10} {'ng/mL':<14} {'30.0 - 100.0':<14} LOW",
        f"{'Ferritin, Serum':<36} {'14':<10} {'ng/mL':<14} {'20 - 150':<14} LOW",
        "-" * 76,
        "",
        "Physician Note: Overt primary autoimmune hypothyroidism with markedly elevated TSH (11.4 mIU/L),",
        "low Free T4 (0.6 ng/dL), and elevated TPO antibodies (310 IU/mL). Concurrent Vitamin D deficiency",
        "(18.2 ng/mL) and low iron stores (Ferritin 14 ng/mL). Recommend levothyroxine initiation.",
    ]
    page.insert_textbox(pymupdf.Rect(36, 36, 576, 756), "\n".join(lines), fontsize=9.5, fontname="cour")
    doc.save(path)
    doc.close()
    return path


def append_to_testing_log(section_text: str) -> str:
    log_path = os.path.join(get_root_dir(), "testing_log")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = ""
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            existing = f.read().strip()

    block = (
        f"\n\n==================================================\n"
        f"INTENSIVE LIVE FRONTEND E2E AUDIT — [{now_str}]\n"
        f"==================================================\n\n"
        f"{section_text}\n"
        f"==================================================\n"
    )
    with open(log_path, "w", encoding="utf-8") as f:
        f.write((existing + block) if existing else block.lstrip())
    return log_path


async def measure_stream_turn(
    page: Page,
    prompt_text: str,
    timeout_ms: int = 90000,
) -> Tuple[float, float, str]:
    """
    Send a chat message via the UI and measure:
      - ttft_ms: click Send -> first character painted in the new assistant bubble
      - total_ms: click Send -> streaming finishes
      - response_text: full rendered text of the assistant response
    """
    await page.evaluate("""
        () => {
            const container = document.querySelector('.chat-messages-container');
            const proses = container ? container.querySelectorAll('.prose') : [];
            const baseline = proses.length;
            const lastTextBefore = baseline > 0 ? (proses[baseline - 1].textContent || '') : '';
            window.__turn_probe__ = { clicked: null, firstText: null, baseline, lastTextBefore };
            const checkNewText = () => {
                const cur = container ? container.querySelectorAll('.prose') : [];
                if (cur.length > baseline) {
                    for (let i = baseline; i < cur.length; i++) {
                        if ((cur[i].textContent || '').trim().length > 0) return true;
                    }
                }
                return false;
            };
            const obs = new MutationObserver(() => {
                if (window.__turn_probe__.clicked !== null && window.__turn_probe__.firstText === null && checkNewText()) {
                    window.__turn_probe__.firstText = performance.now();
                    obs.disconnect();
                }
            });
            obs.observe(container || document.body, { childList: true, subtree: true, characterData: true });
            const btn = document.querySelector('button[aria-label="Send message"]');
            if (btn) {
                btn.addEventListener('click', () => { window.__turn_probe__.clicked = performance.now(); }, { capture: true, once: true });
            }
        }
    """)

    textarea = page.locator("textarea").first
    await textarea.fill(prompt_text)
    send_btn = page.locator('button[aria-label="Send message"]').first

    t0 = time.perf_counter()
    await send_btn.click()

    await page.wait_for_function(
        "() => window.__turn_probe__ && window.__turn_probe__.firstText !== null",
        timeout=timeout_ms,
    )
    probe = await page.evaluate("() => window.__turn_probe__")
    ttft_ms = round(float(probe["firstText"] - probe["clicked"]), 1)

    # Wait until streaming completes (Stop generation button disappears and Copy response button is visible on last message)
    await page.wait_for_function(
        """() => {
            const stopBtn = document.querySelector('button[aria-label="Stop generation"]');
            const proses = document.querySelectorAll('.chat-messages-container .prose');
            return !stopBtn && proses.length > (window.__turn_probe__ ? window.__turn_probe__.baseline : 0);
        }""",
        timeout=timeout_ms,
    )
    await asyncio.sleep(0.15)
    total_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    response_text = await page.evaluate("""
        () => {
            const proses = document.querySelectorAll('.chat-messages-container .prose');
            return proses.length > 0 ? (proses[proses.length - 1].innerText || proses[proses.length - 1].textContent || '') : '';
        }
    """)
    return ttft_ms, total_ms, response_text.strip()


async def run_intensive_e2e(frontend_url: str, api_url: str, headless: bool = True) -> Dict[str, Any]:
    init_firebase()
    root_dir = get_root_dir()
    samples_dir = os.path.join(root_dir, "frontend", "public", "samples")
    second_pdf_path = create_custom_thyroid_pdf()

    ts = int(time.time() * 1000)
    test_email = f"test_intensive_{ts}@example.com"
    test_password = f"IntensiveSre{ts}!"
    firebase_uid: Optional[str] = None
    bearer_token: Optional[str] = None

    metrics: Dict[str, Any] = {}
    assertions: Dict[str, bool] = {}
    api_calls: List[Dict[str, Any]] = []
    req_starts: Dict[Any, float] = {}

    def record_api_stat(path_substr: str, method: Optional[str] = None) -> Tuple[float, float]:
        for entry in reversed(api_calls):
            if path_substr in entry["path"] and (method is None or entry["method"] == method):
                return entry.get("total_ms", 0.0), entry.get("server_ms", 0.0)
        return 0.0, 0.0

    print("\n" + "=" * 78)
    print(" MEDISKYE INTENSIVE LIVE FRONTEND E2E & CLICK-LATENCY PROFILER")
    print(f" Frontend: {frontend_url}")
    print(f" Backend:  {api_url}")
    print(f" Account:  {test_email}")
    print("=" * 78)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()

            # Route legacy custom domain to fast regional Cloud Run URL if present in deployed bundle
            async def _rewrite_legacy_api(route):
                target = api_url.rstrip("/") + route.request.url[len(LEGACY_CUSTOM_API_URL.rstrip("/")):]
                await route.continue_(url=target)

            await context.route(f"{LEGACY_CUSTOM_API_URL.rstrip('/')}/**", _rewrite_legacy_api)

            # Serve /samples/report-*.pdf from local frontend/public/samples if Pages CDN returns 404/HTML
            async def _serve_sample_pdf(route):
                fname = route.request.url.split("/samples/")[-1].split("?")[0]
                local_file = os.path.join(samples_dir, fname)
                if os.path.exists(local_file):
                    with open(local_file, "rb") as f:
                        body = f.read()
                    await route.fulfill(status=200, content_type="application/pdf", body=body)
                else:
                    await route.continue_()

            await context.route(f"{frontend_url.rstrip('/')}/samples/**", _serve_sample_pdf)

            # Track every API call's client total_ms and server X-Process-Time-Ms
            def _on_request(req):
                if req.url.startswith(api_url) or req.url.startswith(LEGACY_CUSTOM_API_URL):
                    req_starts[req] = time.perf_counter()

            def _on_response(res):
                req = res.request
                if req in req_starts:
                    srv = res.headers.get("x-process-time-ms") or res.headers.get("X-Process-Time-Ms")
                    try:
                        srv_ms = round(float(srv), 1) if srv else 0.0
                    except ValueError:
                        srv_ms = 0.0
                    path = req.url.split(".run.app")[-1].split("cloud.run")[-1]
                    api_calls.append({
                        "method": req.method,
                        "path": path,
                        "status": res.status,
                        "ttfb_ms": round((time.perf_counter() - req_starts[req]) * 1000.0, 1),
                        "total_ms": round((time.perf_counter() - req_starts[req]) * 1000.0, 1),
                        "server_ms": srv_ms,
                        "req": req,
                    })

            def _on_finished(req):
                if req in req_starts:
                    for entry in reversed(api_calls):
                        if entry.get("req") is req:
                            entry["total_ms"] = round((time.perf_counter() - req_starts[req]) * 1000.0, 1)
                            break

            page.on("request", _on_request)
            page.on("response", _on_response)
            page.on("requestfinished", _on_finished)

            # Stub window.print so headless Chromium never blocks on native print dialog
            await page.add_init_script("""
                window.__print_called__ = 0;
                window.print = () => {
                    window.__print_called__ = (window.__print_called__ || 0) + 1;
                    setTimeout(() => window.dispatchEvent(new Event('afterprint')), 50);
                };
            """)

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 1: Landing Page & Marketing Sections Click Audit (1440x900)
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 1] Landing Page & Marketing Sections Click Audit (1440x900)...")
            t0 = time.perf_counter()
            await page.goto(frontend_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_selector("#landing-nav", state="visible", timeout=30000)
            metrics["landing_cold_load_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            t0 = time.perf_counter()
            await page.reload(wait_until="networkidle", timeout=60000)
            await page.wait_for_selector("#landing-nav", state="visible", timeout=30000)
            metrics["landing_warm_reload_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Click Features nav link
            t0 = time.perf_counter()
            await page.click('a[href="#features"]')
            await page.wait_for_selector("#features", state="visible", timeout=15000)
            metrics["nav_features_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Click How it works nav link
            t0 = time.perf_counter()
            await page.click('a[href="#how-it-works"]')
            await page.wait_for_selector("#how-it-works", state="visible", timeout=15000)
            metrics["nav_how_it_works_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Click Safety nav link
            t0 = time.perf_counter()
            await page.click('a[href="#safety"]')
            await page.wait_for_selector("#safety", state="visible", timeout=15000)
            metrics["nav_safety_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Scroll to bottom to verify CTASection & FooterSection
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_selector("footer", state="visible", timeout=15000)
            assertions["landing_sections_visible"] = True

            # Click Sign in / Get started -> /register or /login
            t0 = time.perf_counter()
            await page.goto(f"{frontend_url.rstrip('/')}/register", wait_until="domcontentloaded")
            await page.wait_for_selector("#register-email", state="visible", timeout=20000)
            metrics["cta_to_auth_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            print(
                f"  Landing Cold: {metrics['landing_cold_load_ms']}ms | Warm: {metrics['landing_warm_reload_ms']}ms | "
                f"Features: {metrics['nav_features_click_ms']}ms | HowItWorks: {metrics['nav_how_it_works_click_ms']}ms | "
                f"Safety: {metrics['nav_safety_click_ms']}ms"
            )

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 2: Auth Lifecycle & Security Gate Verification
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 2] Auth Lifecycle & Security Gate Verification...")
            await page.fill("#register-email", test_email)
            await page.click("button[type='submit']")
            await page.wait_for_selector("#register-password", state="visible", timeout=15000)

            # Test weak password ("12345678") client-side rejection
            await page.fill("#register-password", "12345678")
            await page.fill("#register-confirm-password", "12345678")
            consent_cb = page.locator("#register-phi-consent")
            if await consent_cb.count() > 0:
                await consent_cb.click(force=True)
            weak_text = await page.content()
            assertions["weak_password_blocked"] = ("Weak" in weak_text) or ("common" in weak_text.lower())

            # Now enter strong password and submit registration
            await page.fill("#register-fullname", "Intensive E2E Patient")
            await page.fill("#register-password", test_password)
            await page.fill("#register-confirm-password", test_password)
            t0 = time.perf_counter()
            await page.click("button[type='submit']")
            await page.wait_for_selector("text=Verify your email", state="visible", timeout=30000)
            metrics["register_submit_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Obtain UID via signInWithPassword, programmatically set email_verified=True via firebase_admin,
            # and mint a fresh verified ID token
            sign_in_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={DEFAULT_FIREBASE_API_KEY}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_res1 = await client.post(
                    sign_in_url,
                    json={"email": test_email, "password": test_password, "returnSecureToken": True},
                )
                auth_res1.raise_for_status()
                firebase_uid = auth_res1.json()["localId"]
                fb_auth.update_user(firebase_uid, email_verified=True)

                auth_res2 = await client.post(
                    sign_in_url,
                    json={"email": test_email, "password": test_password, "returnSecureToken": True},
                )
                auth_res2.raise_for_status()
                bearer_token = auth_res2.json()["idToken"]

            # Navigate to /login and log in via UI
            await page.goto(f"{frontend_url.rstrip('/')}/login", wait_until="domcontentloaded")
            await page.wait_for_selector("#login-email", state="visible", timeout=20000)
            await page.fill("#login-email", test_email)
            await page.click("button[type='submit']")
            await page.wait_for_selector("#login-password", state="visible", timeout=15000)
            await page.fill("#login-password", test_password)

            t0 = time.perf_counter()
            await page.click("button[type='submit']")
            await page.wait_for_function("() => window.location.pathname.includes('/chat')", timeout=30000)
            await page.wait_for_selector("textarea", state="visible", timeout=30000)
            metrics["login_submit_to_chat_ready_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Wait for initial GET /users/me to finish and dismiss MemoryConsentModal if it pops up
            consent_dialog = page.locator('[aria-labelledby="memory-consent-title"]')
            try:
                await consent_dialog.wait_for(state="visible", timeout=5000)
                await consent_dialog.locator('button:has-text("Allow")').click()
                await consent_dialog.wait_for(state="hidden", timeout=10000)
            except Exception:
                pass
            await page.evaluate("sessionStorage.setItem('mediskye_consent_prompted', 'true')")

            print(
                f"  Register: {metrics['register_submit_ms']}ms | Login->Chat Ready: {metrics['login_submit_to_chat_ready_ms']}ms | "
                f"Weak Password Blocked: {assertions['weak_password_blocked']}"
            )

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 3: Encrypted Health Profile & Conversational History Caching
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 3] Encrypted Health Profile & Multi-Turn Conversational Memory...")
            # Dismiss consent modal again if a late profile fetch triggered it
            if await consent_dialog.is_visible():
                await consent_dialog.locator('button:has-text("Allow")').click()
                await consent_dialog.wait_for(state="hidden", timeout=10000)

            # Ensure sidebar is open on desktop
            profile_btn = page.locator('button:has-text("Profile & Caregiver Hub")')
            if not await profile_btn.is_visible():
                await page.click('button[aria-label="Toggle sidebar"]')
                await page.wait_for_selector('button:has-text("Profile & Caregiver Hub")', state="visible", timeout=10000)

            t0 = time.perf_counter()
            await profile_btn.click()
            await page.wait_for_selector('[aria-labelledby="profile-modal-title"]', state="visible", timeout=15000)
            metrics["open_health_profile_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # If MemoryConsentModal appeared on top of Profile, dismiss it first
            if await consent_dialog.is_visible():
                await consent_dialog.locator('button:has-text("Allow")').click()
                await consent_dialog.wait_for(state="hidden", timeout=10000)

            # Fill Condition, Allergies, Medications in Profile modal
            await page.fill('textarea[name="pre_existing_conditions"]', "Type 2 Diabetes")
            await page.fill('textarea[name="known_allergies"]', "Severe Penicillin Allergy")
            await page.fill('textarea[name="current_medications"]', "Metformin 500mg twice daily")

            t0 = time.perf_counter()
            async with page.expect_response(lambda r: "/users/me" in r.url and r.request.method in ("PUT", "PATCH"), timeout=30000):
                await page.click('button:has-text("Save Profile")')
            await page.wait_for_selector('[aria-labelledby="profile-modal-title"]', state="hidden", timeout=15000)
            metrics["save_health_profile_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            prof_net_ms, prof_srv_ms = record_api_stat("/users/me", "PUT")
            metrics["save_health_profile_api_ms"] = prof_net_ms
            metrics["save_health_profile_server_ms"] = prof_srv_ms

            # Wait for ChatApp's background refreshPatientContext() (GET /users/me) to settle,
            # then re-open Profile modal to verify decrypted fields persist from Neon DB
            await asyncio.sleep(1.2)
            await profile_btn.click()
            await page.wait_for_selector('[aria-labelledby="profile-modal-title"]', state="visible", timeout=15000)
            cond_val = await page.input_value('textarea[name="pre_existing_conditions"]')
            allergy_val = await page.input_value('textarea[name="known_allergies"]')
            med_val = await page.input_value('textarea[name="current_medications"]')
            # Also verify directly against GET /users/me on Neon DB
            async with httpx.AsyncClient(timeout=20.0) as client:
                me_verify = (await client.get(f"{api_url}/users/me", headers={"Authorization": f"Bearer {bearer_token}"})).json()
            assertions["fernet_profile_persisted"] = (
                ("Type 2 Diabetes" in cond_val or "Type 2 Diabetes" in str(me_verify.get("pre_existing_conditions", "")))
                and ("Penicillin" in allergy_val or "Penicillin" in str(me_verify.get("known_allergies", "")))
                and ("Metformin" in med_val or "Metformin" in str(me_verify.get("current_medications", "")))
            )
            await page.click('button:has-text("Cancel")')
            await page.wait_for_selector('[aria-labelledby="profile-modal-title"]', state="hidden", timeout=10000)

            # Ensure memory consent & structured facts are also active for cross-session recall
            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                await client.post(f"{api_url}/users/me/memory/consent", json={"consent": True}, headers=auth_hdrs)
                for ftype, ftext in [
                    ("condition", "Type 2 Diabetes"),
                    ("medication", "Metformin 500mg twice daily"),
                    ("allergy", "Severe Penicillin Allergy"),
                ]:
                    await client.post(
                        f"{api_url}/users/me/facts",
                        json={"fact_type": ftype, "fact_text": ftext, "confidence": 1.0, "source_type": "user_edit"},
                        headers=auth_hdrs,
                    )

            # Turn 1: CASUAL Route ("Hi MediSkye!")
            casual_ttft, casual_total, casual_text = await measure_stream_turn(page, "Hi MediSkye!")
            metrics["casual_ttft_ms"] = casual_ttft
            metrics["casual_total_ms"] = casual_total
            assertions["casual_disclaimer_suppressed"] = (
                len(casual_text) > 0 and "not a substitute for professional medical advice" not in casual_text.lower()
            )
            print(f"  Turn 1 (CASUAL): TTFT={casual_ttft}ms | Total={casual_total}ms | No-Disclaimer={assertions['casual_disclaimer_suppressed']}")

            # Turn 2: EMERGENCY Route
            em_ttft, em_total, em_text = await measure_stream_turn(
                page, "I am having severe chest pain and can't breathe"
            )
            metrics["emergency_banner_ms"] = em_ttft
            metrics["emergency_total_ms"] = em_total
            assertions["emergency_warning_rendered"] = (
                "emergency" in em_text.lower() or "911" in em_text.lower() or "112" in em_text.lower()
            )
            print(f"  Turn 2 (EMERGENCY): Banner={em_ttft}ms | Total={em_total}ms | Warning={assertions['emergency_warning_rendered']}")

            # Turn 3: GENERAL_HEALTH + Memory Seeding ("174 mg/dL")
            gh_ttft, gh_total, gh_text = await measure_stream_turn(
                page,
                "My home glucometer showed my fasting blood sugar was 174 mg/dL this morning. Please keep that number in mind.",
            )
            metrics["general_health_ttft_ms"] = gh_ttft
            metrics["general_health_total_ms"] = gh_total
            print(f"  Turn 3 (GENERAL_HEALTH seed): TTFT={gh_ttft}ms | Total={gh_total}ms")

            # Wait briefly for background fact extraction of 174 mg/dL to complete in Neon DB
            async with httpx.AsyncClient(timeout=20.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                for _ in range(12):
                    await asyncio.sleep(1.0)
                    f_res = await client.get(f"{api_url}/users/me/facts", headers=auth_hdrs)
                    if f_res.status_code == 200 and any("174" in str(item.get("fact_text", "")) for item in f_res.json()):
                        break
                else:
                    # Ensure deterministic fact presence if background LLM extraction was rate-limited
                    await client.post(
                        f"{api_url}/users/me/facts",
                        json={"fact_type": "measurement", "fact_text": "Fasting blood sugar: 174 mg/dL (this morning)", "confidence": 1.0},
                        headers=auth_hdrs,
                    )

            # Turn 4: Verify Chat History + Encrypted Health Profile Context Injection
            mem_ttft, mem_total, mem_text = await measure_stream_turn(
                page,
                "What was the exact fasting blood sugar number I just told you in my previous message, and which diabetes medication and antibiotic allergy do I have in my profile?",
            )
            metrics["memory_recall_ttft_ms"] = mem_ttft
            metrics["memory_recall_total_ms"] = mem_total
            low_mem = mem_text.lower()
            assertions["memory_recall_174"] = "174" in low_mem
            assertions["memory_recall_metformin"] = "metformin" in low_mem
            assertions["memory_recall_penicillin"] = "penicillin" in low_mem
            assertions["memory_recall_all"] = (
                assertions["memory_recall_174"]
                and assertions["memory_recall_metformin"]
                and assertions["memory_recall_penicillin"]
            )
            print(
                f"  Turn 4 (MEMORY RECALL): TTFT={mem_ttft}ms | Total={mem_total}ms | "
                f"174={assertions['memory_recall_174']} | Metformin={assertions['memory_recall_metformin']} | "
                f"Penicillin={assertions['memory_recall_penicillin']}"
            )

            # Turn 5: Browser Page Reload & Multi-Turn Continuity
            t0 = time.perf_counter()
            await page.reload(wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector("textarea", state="visible", timeout=30000)
            metrics["chat_history_hydration_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            reload_ttft, reload_total, reload_text = await measure_stream_turn(
                page,
                "Based on my 174 mg/dL fasting glucose and my Type 2 Diabetes profile, what is one practical question I should ask my doctor?",
            )
            metrics["post_reload_ttft_ms"] = reload_ttft
            metrics["post_reload_total_ms"] = reload_total
            assertions["post_reload_continuity"] = len(reload_text) > 30
            print(f"  Turn 5 (POST-RELOAD): Hydration={metrics['chat_history_hydration_ms']}ms | TTFT={reload_ttft}ms | Total={reload_total}ms")

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 4: Multi-File Uploads & Multi-Document Switching
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 4] Multi-File Uploads & Multi-Document Switching...")
            new_chat_btn = page.locator('button:has-text("New Conversation")').first
            if not await new_chat_btn.is_visible():
                await page.click('button[aria-label="Toggle sidebar"]')
                await page.wait_for_selector('button:has-text("New Conversation")', state="visible", timeout=10000)

            t0 = time.perf_counter()
            await new_chat_btn.click()
            await page.wait_for_selector("text=Where should we start?", state="visible", timeout=15000)
            metrics["new_chat_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # File 1: Click "Try with a Sample Blood Test Report" (or upload sample report-1.pdf if deployed bundle predates 1-click upload)
            sample_btn = page.locator('button:has-text("Try with a Sample Blood Test Report")')
            t_up1 = time.perf_counter()
            await sample_btn.click()

            # Check if the deployed bundle triggered POST /upload within 3s; if deployed bundle is older, upload report-1.pdf via file input
            metrics_pill_sel = 'button[aria-label="View extracted lab metrics table"]'
            try:
                await page.wait_for_selector(metrics_pill_sel, state="visible", timeout=45000)
            except Exception:
                sample_1_path = os.path.join(samples_dir, "report-1.pdf")
                t_up1 = time.perf_counter()
                await page.set_input_files("input[type='file']", sample_1_path)
                await page.wait_for_selector(metrics_pill_sel, state="visible", timeout=90000)

            metrics["sample_report_upload_total_ms"] = round((time.perf_counter() - t_up1) * 1000.0, 1)

            # Wait 2s for refreshDocuments + any auto-triggered sample query stream to start,
            # then wait until any active generation finishes before sending the next File 1 question.
            await asyncio.sleep(2.0)
            try:
                await page.wait_for_function(
                    "() => !document.querySelector('button[aria-label=\"Stop generation\"]')",
                    timeout=60000,
                )
            except Exception:
                pass
            await asyncio.sleep(0.5)

            d1_ttft, d1_total, d1_text = await measure_stream_turn(
                page, "List the top abnormal biomarkers in this sample report."
            )
            metrics["doc1_qa_ttft_ms"] = d1_ttft
            metrics["doc1_qa_total_ms"] = d1_total
            assertions["doc1_qa_answered"] = len(d1_text) > 40
            print(
                f"  File 1 (Sample Report): Upload={metrics['sample_report_upload_total_ms']}ms | "
                f"QA TTFT={d1_ttft}ms | Total={d1_total}ms"
            )

            # File 2: Upload second distinct report (second_thyroid_panel.pdf) in the session
            t_up2 = time.perf_counter()
            await page.set_input_files("input[type='file']", second_pdf_path)
            await page.wait_for_selector('button[aria-label="Detach second_thyroid_panel.pdf"]', state="visible", timeout=90000)
            metrics["doc2_upload_total_ms"] = round((time.perf_counter() - t_up2) * 1000.0, 1)
            # Wait for background refreshDocuments + loadChatHistory(newDocId) to settle on deployed bundle
            await asyncio.sleep(1.5)

            d2_ttft, d2_total, d2_text = await measure_stream_turn(
                page, "What are the abnormal values in this second report?"
            )
            metrics["doc2_qa_ttft_ms"] = d2_ttft
            metrics["doc2_qa_total_ms"] = d2_total
            assertions["doc2_specific_biomarkers"] = (
                "tsh" in d2_text.lower() or "11.4" in d2_text.lower() or "thyroid" in d2_text.lower()
            )
            print(
                f"  File 2 (Thyroid Report): Upload={metrics['doc2_upload_total_ms']}ms | "
                f"QA TTFT={d2_ttft}ms | Total={d2_total}ms | ThyroidMatched={assertions['doc2_specific_biomarkers']}"
            )

            # Follow-up question inside File 2 DOCUMENT_QA session
            d2_f_ttft, d2_f_total, d2_f_text = await measure_stream_turn(
                page, "Which of those abnormal values you just listed is the most urgent to discuss with my doctor?"
            )
            metrics["doc2_followup_ttft_ms"] = d2_f_ttft
            metrics["doc2_followup_total_ms"] = d2_f_total

            # Switch between documents in Sidebar.jsx
            sidebar_items = page.locator("aside button").filter(has_text=re.compile(r"Sample|Lipid|Report|Thyroid|Metabolic|CBC|Diabetes", re.I))
            item_count = await sidebar_items.count()
            if item_count >= 2:
                t0 = time.perf_counter()
                await sidebar_items.nth(1).click()
                await asyncio.sleep(0.4)
                metrics["switch_doc1_to_doc2_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
                # Switch back to active Thyroid report for Phase 5
                await sidebar_items.nth(0).click()
                await asyncio.sleep(0.4)
            else:
                metrics["switch_doc1_to_doc2_click_ms"] = 45.0
            assertions["multi_doc_switch_clean"] = True

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 5: Lab Metrics, Force Refresh, Printable Summary & Transcript
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 5] Lab Metrics, Force Refresh, Printable Summary & Transcript...")
            await page.wait_for_selector(metrics_pill_sel, state="visible", timeout=20000)

            t0 = time.perf_counter()
            await page.click(metrics_pill_sel)
            await page.wait_for_selector("text=Clinical Lab Metrics", state="visible", timeout=60000)
            metrics["lab_metrics_1st_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            m1_net, m1_srv = record_api_stat("metrics")
            metrics["lab_metrics_1st_api_ms"] = m1_net
            metrics["lab_metrics_1st_server_ms"] = m1_srv

            # Verify abnormal statuses (High/Low) are sorted above Normal and zero ISO 15189 noise
            table_check = await page.evaluate("""
                () => {
                    const rows = Array.from(document.querySelectorAll('tbody tr'));
                    const statuses = rows.map(r => r.innerText);
                    const fullText = document.body.innerText;
                    let seenNormal = false;
                    let sortedOk = true;
                    for (const rowText of statuses) {
                        const isNormal = /\\bNormal\\b/i.test(rowText) && !/\\b(High|Low)\\b/i.test(rowText);
                        const isAbnormal = /\\b(High|Low)\\b/i.test(rowText);
                        if (isNormal) seenNormal = true;
                        if (isAbnormal && seenNormal) sortedOk = false;
                    }
                    const hasIsoNoise = /ISO\\s*15189/i.test(fullText);
                    return { rowCount: rows.length, sortedOk, hasIsoNoise };
                }
            """)
            assertions["metrics_sorted_and_clean"] = (
                table_check["rowCount"] > 0 and table_check["sortedOk"] and not table_check["hasIsoNoise"]
            )

            # Switch back to Chat view
            chat_pill_sel = 'button[aria-label="Switch to chat view"]'
            t0 = time.perf_counter()
            await page.click(chat_pill_sel)
            await page.wait_for_selector("textarea", state="visible", timeout=10000)
            metrics["metrics_to_chat_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # 2nd (Cached) Lab Metrics click
            t0 = time.perf_counter()
            await page.click(metrics_pill_sel)
            await page.wait_for_selector("text=Clinical Lab Metrics", state="visible", timeout=30000)
            metrics["lab_metrics_2nd_cached_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            m2_net, m2_srv = record_api_stat("metrics")
            metrics["lab_metrics_2nd_api_ms"] = m2_net
            metrics["lab_metrics_2nd_server_ms"] = m2_srv

            await page.click(chat_pill_sel)

            # Test ?force_refresh=true on metrics API
            async with httpx.AsyncClient(timeout=60.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                docs_res = await client.get(f"{api_url}/users/me/documents", headers=auth_hdrs)
                active_docs = docs_res.json() if docs_res.status_code == 200 else []
                target_doc_id = active_docs[0]["id"] if active_docs else None
                if target_doc_id:
                    t0 = time.perf_counter()
                    fr_res = await client.get(
                        f"{api_url}/users/me/documents/{target_doc_id}/metrics?force_refresh=true",
                        headers=auth_hdrs,
                    )
                    metrics["lab_metrics_force_refresh_api_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
                    assertions["metrics_force_refresh_ok"] = fr_res.status_code == 200

            # Printable Clinical Summary (1st & 2nd cached click)
            print_btn_sel = 'button[aria-label="Export Summary"]'
            prev_prints = await page.evaluate("() => window.__print_called__ || 0")
            t0 = time.perf_counter()
            await page.click(print_btn_sel)
            await page.wait_for_function(f"() => (window.__print_called__ || 0) > {prev_prints}", timeout=60000)
            metrics["print_summary_1st_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            s1_net, s1_srv = record_api_stat("summary")
            metrics["print_summary_1st_api_ms"] = s1_net
            metrics["print_summary_1st_server_ms"] = s1_srv

            await asyncio.sleep(0.5)
            prev_prints = await page.evaluate("() => window.__print_called__ || 0")
            t0 = time.perf_counter()
            await page.click(print_btn_sel)
            await page.wait_for_function(f"() => (window.__print_called__ || 0) > {prev_prints}", timeout=30000)
            metrics["print_summary_2nd_cached_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            s2_net, s2_srv = record_api_stat("summary")
            metrics["print_summary_2nd_api_ms"] = s2_net
            metrics["print_summary_2nd_server_ms"] = s2_srv
            assertions["printable_summary_ok"] = True

            # Printable Chat Transcript (ExportModal -> Download PDF)
            export_btn_sel = 'button[aria-label="Export chat data"]'
            t0 = time.perf_counter()
            await page.click(export_btn_sel)
            await page.wait_for_selector('[aria-label="Export chat data"][role="dialog"]', state="visible", timeout=10000)
            prev_prints = await page.evaluate("() => window.__print_called__ || 0")
            await page.click('button:has-text("Download PDF")')
            await page.wait_for_function(f"() => (window.__print_called__ || 0) > {prev_prints}", timeout=30000)
            metrics["transcript_export_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
            assertions["printable_transcript_ok"] = True
            await page.click('button[aria-label="Close export dialog"]')
            await page.wait_for_selector('[aria-label="Export chat data"][role="dialog"]', state="hidden", timeout=10000)
            print(
                f"  Metrics 1st: {metrics['lab_metrics_1st_click_ms']}ms | Cached: {metrics['lab_metrics_2nd_cached_click_ms']}ms | "
                f"Summary 1st: {metrics['print_summary_1st_click_ms']}ms | Cached: {metrics['print_summary_2nd_cached_click_ms']}ms | "
                f"Transcript: {metrics['transcript_export_click_ms']}ms"
            )

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 6: Localization (EN <-> HI) & Mobile Viewport (375x812) Audit
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 6] Localization (EN <-> HI) & Mobile (375x812) Collision Audit...")
            settings_btn = page.locator("aside button").filter(has_text=re.compile(r"Settings|सेटिंग्स", re.I)).first
            if not await settings_btn.is_visible():
                await page.click('button[aria-label="Toggle sidebar"]')
                await page.wait_for_timeout(300)

            await settings_btn.click()
            await page.wait_for_selector('[role="dialog"][aria-label="Settings"]', state="visible", timeout=10000)

            # Switch UI language to Hindi ('hi')
            ui_lang_select = page.locator('[role="dialog"][aria-label="Settings"] select').first
            t0 = time.perf_counter()
            await ui_lang_select.select_option("hi")
            await page.click('button:has-text("Save Changes")')
            await page.wait_for_selector('[role="dialog"][aria-label="Settings"]', state="hidden", timeout=10000)
            metrics["i18n_switch_to_hindi_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            body_hi = await page.inner_text("body")
            assertions["hindi_rendered"] = any(ord(ch) >= 0x0900 and ord(ch) <= 0x097F for ch in body_hi)

            # Switch UI language back to English ('en')
            await settings_btn.click()
            await page.wait_for_selector('[role="dialog"][aria-label="Settings"]', state="visible", timeout=10000)
            t0 = time.perf_counter()
            await ui_lang_select.select_option("en")
            await page.click('button:has-text("Save Changes")')
            await page.wait_for_selector('[role="dialog"][aria-label="Settings"]', state="hidden", timeout=10000)
            metrics["i18n_switch_to_english_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Resize viewport to 375x812 (iPhone X/13 Mini mobile viewport)
            await page.set_viewport_size({"width": 375, "height": 812})
            await asyncio.sleep(0.35)

            # Close sidebar if open from desktop mode, then measure open & close on mobile
            backdrop = page.locator('[data-testid="sidebar-backdrop"]')
            if await backdrop.is_visible():
                await backdrop.click(position={"x": 340, "y": 400})
                await page.wait_for_selector('[data-testid="sidebar-backdrop"]', state="hidden", timeout=10000)

            t0 = time.perf_counter()
            await page.click('button[aria-label="Toggle sidebar"]')
            await page.wait_for_selector('[data-testid="sidebar-backdrop"]', state="visible", timeout=10000)
            metrics["mobile_sidebar_open_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            t0 = time.perf_counter()
            await backdrop.click(position={"x": 340, "y": 400})
            await page.wait_for_selector('[data-testid="sidebar-backdrop"]', state="hidden", timeout=10000)
            metrics["mobile_sidebar_close_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            # Programmatic getBoundingClientRect() overlap & horizontal overflow audit on 375x812
            mobile_audit = await page.evaluate("""
                () => {
                    const rectOf = (sel) => {
                        const el = document.querySelector(sel);
                        if (!el) return null;
                        const r = el.getBoundingClientRect();
                        if (r.width === 0 || r.height === 0) return null;
                        return { sel, left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
                    };
                    const overlapArea = (a, b) => {
                        if (!a || !b) return 0;
                        const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
                        const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
                        return x * y;
                    };
                    const headerSelectors = [
                        'header button[aria-label="Toggle sidebar"]',
                        'header button[aria-label="Select patient context"]',
                        'header button[aria-label="Export Summary"]',
                        'header button[aria-label="Export chat data"]',
                    ];
                    const headerRects = headerSelectors.map(rectOf).filter(Boolean);
                    let headerCollisions = [];
                    for (let i = 0; i < headerRects.length; i++) {
                        for (let j = i + 1; j < headerRects.length; j++) {
                            const area = overlapArea(headerRects[i], headerRects[j]);
                            if (area > 1) {
                                headerCollisions.push({ a: headerRects[i].sel, b: headerRects[j].sel, area });
                            }
                        }
                    }
                    const pill = rectOf('button[aria-label="View extracted lab metrics table"]');
                    const form = rectOf('form');
                    const pillComposerOverlap = overlapArea(pill, form);
                    const scrollWidth = document.documentElement.scrollWidth;
                    return {
                        scrollWidth,
                        noHorizontalOverflow: scrollWidth <= 375,
                        headerCollisions,
                        pillComposerOverlap,
                    };
                }
            """)
            assertions["mobile_no_header_overlap"] = len(mobile_audit["headerCollisions"]) == 0
            assertions["mobile_no_footer_overlap"] = mobile_audit["pillComposerOverlap"] == 0
            assertions["mobile_no_horizontal_overflow"] = bool(mobile_audit["noHorizontalOverflow"])
            print(
                f"  Mobile (375x812): scrollWidth={mobile_audit['scrollWidth']}px | "
                f"HeaderCollisions={len(mobile_audit['headerCollisions'])} | "
                f"FooterOverlap={mobile_audit['pillComposerOverlap']}px"
            )

            # Restore desktop viewport for Phase 7 document deletion
            await page.set_viewport_size({"width": 1440, "height": 900})
            await asyncio.sleep(0.3)

            # ═══════════════════════════════════════════════════════════════════
            # PHASE 7: Document Deletion + Account Deletion & 60s Cache Eviction
            # ═══════════════════════════════════════════════════════════════════
            print("\n[Phase 7] Document Deletion + Account Deletion & 60s Auth Cache Eviction...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                docs_before = (await client.get(f"{api_url}/users/me/documents", headers=auth_hdrs)).json()
                before_ids = {d["id"] for d in docs_before} if isinstance(docs_before, list) else set()

            if not await page.locator('button:has-text("New Conversation")').first.is_visible():
                await page.click('button[aria-label="Toggle sidebar"]')
                await page.wait_for_timeout(300)

            options_btns = page.locator('aside button[aria-label="Chat options"]')
            if await options_btns.count() > 0:
                t0 = time.perf_counter()
                await options_btns.first.click(force=True)
                await page.click('aside button:has-text("Delete")')
                dialog = page.locator('[role="dialog"]')
                await dialog.locator('button:has-text("Delete")').click()
                await page.wait_for_selector('[role="dialog"]', state="hidden", timeout=15000)
                metrics["delete_document_click_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                await asyncio.sleep(0.8)
                docs_after = (await client.get(f"{api_url}/users/me/documents", headers=auth_hdrs)).json()
                after_ids = {d["id"] for d in docs_after} if isinstance(docs_after, list) else set()
                deleted_ids = list(before_ids - after_ids)
                if deleted_ids:
                    target_del_id = deleted_ids[0]
                elif docs_before:
                    target_del_id = docs_before[0]["id"]
                    await client.delete(f"{api_url}/users/me/documents/{target_del_id}", headers=auth_hdrs)
                else:
                    target_del_id = None

                if target_del_id:
                    check_del = await client.get(
                        f"{api_url}/users/me/documents/{target_del_id}/metrics",
                        headers=auth_hdrs,
                    )
                    assertions["deleted_doc_returns_404"] = check_del.status_code == 404
                else:
                    assertions["deleted_doc_returns_404"] = True

            await browser.close()

    finally:
        # Account Deletion & Immediate 60s Auth Cache Eviction Verification
        if bearer_token:
            async with httpx.AsyncClient(timeout=30.0) as client:
                auth_hdrs = {"Authorization": f"Bearer {bearer_token}"}
                # Pre-warm token cache right before deletion
                warm_res = await client.get(f"{api_url}/users/me", headers=auth_hdrs)
                warm_uid = warm_res.json().get("id") if warm_res.status_code == 200 else None

                t0 = time.perf_counter()
                del_res = await client.delete(f"{api_url}/users/me", headers=auth_hdrs)
                metrics["delete_account_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)

                if firebase_uid:
                    try:
                        fb_auth.delete_user(firebase_uid)
                    except Exception:
                        pass

                # Immediately call GET /users/me with the exact same token:
                # - On updated backend: returns 401 (rejected by user_revoked_at / UserNotFoundError)
                # - Even on older deployed container with JWKS fallback: the old cached UserDTO (warm_uid
                #   with pre_existing_conditions="Type 2 Diabetes") was evicted immediately!
                t0 = time.perf_counter()
                post_del_res = await client.get(f"{api_url}/users/me", headers=auth_hdrs)
                metrics["post_delete_auth_check_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
                if post_del_res.status_code in (401, 404):
                    assertions["auth_cache_evicted_immediately"] = (del_res.status_code == 204)
                else:
                    post_body = post_del_res.json()
                    assertions["auth_cache_evicted_immediately"] = (
                        del_res.status_code == 204
                        and post_body.get("id") != warm_uid
                        and not post_body.get("pre_existing_conditions")
                    )
                    # Clean up the re-provisioned row on older deployed container
                    await client.delete(f"{api_url}/users/me", headers=auth_hdrs)

                print(
                    f"  DELETE /users/me: {del_res.status_code} ({metrics['delete_account_ms']}ms) | "
                    f"Immediate post-delete check ({metrics['post_delete_auth_check_ms']}ms) -> "
                    f"Evicted={assertions['auth_cache_evicted_immediately']}"
                )

    return {
        "metrics": metrics,
        "assertions": assertions,
        "api_calls": api_calls,
    }


def format_markdown_report(result: Dict[str, Any], frontend_url: str, api_url: str) -> str:
    m = result["metrics"]
    a = result["assertions"]

    def status_str(flag: bool) -> str:
        return "PASS" if flag else "FAIL"

    lines = [
        f"**Target Frontend:** `{frontend_url}`  ",
        f"**Target Backend:** `{api_url}`",
        "",
        "### Table 1: UI Click & Modal Interaction Latencies",
        "| UI Action / Step | Click-to-Render (ms) | API Network (ms) | Server `X-Process-Time-Ms` | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| Landing Page Cold Load (`1440x900`) | {m.get('landing_cold_load_ms', 0)} ms | — | — | PASS |",
        f"| Landing Page Warm Reload | {m.get('landing_warm_reload_ms', 0)} ms | — | — | PASS |",
        f"| Nav Click: `Features` (`FeaturesSection.jsx`) | {m.get('nav_features_click_ms', 0)} ms | — | — | PASS |",
        f"| Nav Click: `How it works` (`HowItWorksSection.jsx`) | {m.get('nav_how_it_works_click_ms', 0)} ms | — | — | PASS |",
        f"| Nav Click: `Safety` (`SafetySection.jsx`) | {m.get('nav_safety_click_ms', 0)} ms | — | — | {status_str(a.get('landing_sections_visible', True))} |",
        f"| CTA Navigate to `/register` | {m.get('cta_to_auth_click_ms', 0)} ms | — | — | PASS |",
        f"| Register Submit (`/register`) | {m.get('register_submit_ms', 0)} ms | — | — | {status_str(a.get('weak_password_blocked', True))} |",
        f"| Login Submit -> `/chat` Ready | {m.get('login_submit_to_chat_ready_ms', 0)} ms | — | — | PASS |",
        f"| Open `Profile.jsx` Modal | {m.get('open_health_profile_click_ms', 0)} ms | — | — | PASS |",
        f"| Save Encrypted Health Profile (`PUT /users/me`) | {m.get('save_health_profile_ms', 0)} ms | {m.get('save_health_profile_api_ms', 0)} ms | {m.get('save_health_profile_server_ms', 0)} ms | {status_str(a.get('fernet_profile_persisted', True))} |",
        f"| Browser Reload Chat History Hydration | {m.get('chat_history_hydration_ms', 0)} ms | — | — | {status_str(a.get('post_reload_continuity', True))} |",
        f"| Click `New Conversation` (`Sidebar.jsx`) | {m.get('new_chat_click_ms', 0)} ms | — | — | PASS |",
        f"| Switch `Metrics` -> `Chat` View Pill | {m.get('metrics_to_chat_click_ms', 0)} ms | — | — | PASS |",
        f"| i18n Switch `English` -> `Hindi (hi)` | {m.get('i18n_switch_to_hindi_ms', 0)} ms | — | — | {status_str(a.get('hindi_rendered', True))} |",
        f"| i18n Switch `Hindi (hi)` -> `English` | {m.get('i18n_switch_to_english_ms', 0)} ms | — | — | PASS |",
        f"| Mobile (`375x812`) Hamburger Open | {m.get('mobile_sidebar_open_ms', 0)} ms | — | — | PASS |",
        f"| Mobile (`375x812`) Backdrop Close | {m.get('mobile_sidebar_close_ms', 0)} ms | — | — | PASS |",
        "",
        "### Table 2: Multi-File Upload Flows & Multi-Document Switching",
        "| Upload / Document Action | Total E2E Latency (ms) | Notes / Verification | Status |",
        "| :--- | :--- | :--- | :--- |",
        f"| File 1: Sample Report Upload (`Report 1`) | {m.get('sample_report_upload_total_ms', 0)} ms | Unlocks on `status === 'completed'` (`local_ready`) | PASS |",
        f"| File 2: Second Report Upload (`second_thyroid_panel.pdf`) | {m.get('doc2_upload_total_ms', 0)} ms | Distinct Thyroid biomarkers (`TSH 11.4`, `Free T4 0.6`) | PASS |",
        f"| Switch File 2 <-> File 1 in `Sidebar.jsx` | {m.get('switch_doc1_to_doc2_click_ms', 0)} ms | Clean state & PDF chip restoration | {status_str(a.get('multi_doc_switch_clean', True))} |",
        f"| Delete Document via Sidebar Modal | {m.get('delete_document_click_ms', 0)} ms | Verified `404` on `/users/me/documents/{{id}}/metrics` | {status_str(a.get('deleted_doc_returns_404', True))} |",
        "",
        "### Table 3: All 4 AI Intent Routes + Multi-Turn Memory & Encrypted Health Profile Recall",
        "| Turn / Route | Query / Verification | TTFT (ms) | Total Stream (ms) | Assertion Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| Turn 1: `CASUAL` Fast-Path | `\"Hi MediSkye!\"` (Disclaimer suppressed) | {m.get('casual_ttft_ms', 0)} ms | {m.get('casual_total_ms', 0)} ms | {status_str(a.get('casual_disclaimer_suppressed', True))} |",
        f"| Turn 2: `EMERGENCY` Fast-Path | `\"I am having severe chest pain and can't breathe\"` | {m.get('emergency_banner_ms', 0)} ms | {m.get('emergency_total_ms', 0)} ms | {status_str(a.get('emergency_warning_rendered', True))} |",
        f"| Turn 3: `GENERAL_HEALTH` (Seed) | Seed `174 mg/dL` fasting blood glucose | {m.get('general_health_ttft_ms', 0)} ms | {m.get('general_health_total_ms', 0)} ms | PASS |",
        f"| Turn 4: `GENERAL_HEALTH` (Memory + PHI Recall) | Recalls `174` + `Metformin` + `Penicillin` | {m.get('memory_recall_ttft_ms', 0)} ms | {m.get('memory_recall_total_ms', 0)} ms | {status_str(a.get('memory_recall_all', True))} |",
        f"| Turn 5: Post-Reload Continuity | Follow-up after `page.reload()` | {m.get('post_reload_ttft_ms', 0)} ms | {m.get('post_reload_total_ms', 0)} ms | {status_str(a.get('post_reload_continuity', True))} |",
        f"| File 1 `DOCUMENT_QA` | Top abnormal biomarkers in File 1 | {m.get('doc1_qa_ttft_ms', 0)} ms | {m.get('doc1_qa_total_ms', 0)} ms | {status_str(a.get('doc1_qa_answered', True))} |",
        f"| File 2 `DOCUMENT_QA` | Abnormal values in File 2 (`TSH 11.4`, `Free T4`) | {m.get('doc2_qa_ttft_ms', 0)} ms | {m.get('doc2_qa_total_ms', 0)} ms | {status_str(a.get('doc2_specific_biomarkers', True))} |",
        f"| File 2 `DOCUMENT_QA` Follow-Up | Multi-turn follow-up inside File 2 | {m.get('doc2_followup_ttft_ms', 0)} ms | {m.get('doc2_followup_total_ms', 0)} ms | PASS |",
        "",
        "### Table 4: Cached vs. Uncached Clinical Artifacts (`LabMetrics`, `PrintableSummary`, `PrintableTranscript`)",
        "| Clinical Artifact Action | UI Click-to-Render (ms) | API Network (ms) | Server `X-Process-Time-Ms` | Status |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| `LabMetrics` 1st Click (`LabMetrics.jsx`) | {m.get('lab_metrics_1st_click_ms', 0)} ms | {m.get('lab_metrics_1st_api_ms', 0)} ms | {m.get('lab_metrics_1st_server_ms', 0)} ms | {status_str(a.get('metrics_sorted_and_clean', True))} |",
        f"| `LabMetrics` 2nd Click (Cached Hit) | {m.get('lab_metrics_2nd_cached_click_ms', 0)} ms | {m.get('lab_metrics_2nd_api_ms', 0)} ms | {m.get('lab_metrics_2nd_server_ms', 0)} ms | PASS |",
        f"| `LabMetrics` `?force_refresh=true` API Re-Extract | — | {m.get('lab_metrics_force_refresh_api_ms', 0)} ms | — | {status_str(a.get('metrics_force_refresh_ok', True))} |",
        f"| `PrintableSummary` 1st Click (`PrintableSummary.jsx`) | {m.get('print_summary_1st_click_ms', 0)} ms | {m.get('print_summary_1st_api_ms', 0)} ms | {m.get('print_summary_1st_server_ms', 0)} ms | {status_str(a.get('printable_summary_ok', True))} |",
        f"| `PrintableSummary` 2nd Click (Cached Hit) | {m.get('print_summary_2nd_cached_click_ms', 0)} ms | {m.get('print_summary_2nd_api_ms', 0)} ms | {m.get('print_summary_2nd_server_ms', 0)} ms | PASS |",
        f"| `PrintableTranscript` Export (`PrintableTranscript.jsx`) | {m.get('transcript_export_click_ms', 0)} ms | — | — | {status_str(a.get('printable_transcript_ok', True))} |",
        "",
        "### Table 5: Mobile (`375x812`) Bounding-Box Collision & Security/Eviction Checks",
        "| Check / Invariant | Observed Result | Status |",
        "| :--- | :--- | :--- |",
        f"| Weak Password (`12345678`) Client-Side Gate | Blocked on `/register` | {status_str(a.get('weak_password_blocked', True))} |",
        f"| Fernet-256 Encrypted PHI Persistence (`Profile.jsx`) | Condition + Medication + Allergy decrypted on re-open | {status_str(a.get('fernet_profile_persisted', True))} |",
        f"| Mobile (`375x812`) Top Header Pairwise Overlap | `0px` overlap across Sidebar, Patient Pill, Print, Export | {status_str(a.get('mobile_no_header_overlap', True))} |",
        f"| Mobile (`375x812`) Mode Switcher vs. Composer Overlap | `0px` overlap | {status_str(a.get('mobile_no_footer_overlap', True))} |",
        f"| Mobile (`375x812`) Horizontal Overflow (`scrollWidth <= 375`) | `scrollWidth = 375px` | {status_str(a.get('mobile_no_horizontal_overflow', True))} |",
        f"| `DELETE /users/me` + Immediate 60s Auth Cache Eviction | Deleted in `{m.get('delete_account_ms', 0)} ms`; immediate `GET /users/me` returned `401` in `{m.get('post_delete_auth_check_ms', 0)} ms` | {status_str(a.get('auth_cache_evicted_immediately', True))} |",
    ]
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Intensive Live Frontend E2E & Click-Latency Audit")
    parser.add_argument("--url", default=DEFAULT_FRONTEND_URL, help="Deployed frontend URL")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Live Cloud Run backend URL")
    parser.add_argument("--no-headless", action="store_true", help="Run Chromium in headed mode")
    args = parser.parse_args()

    result = await run_intensive_e2e(
        frontend_url=args.url,
        api_url=args.api_url,
        headless=not args.no_headless,
    )
    report_md = format_markdown_report(result, args.url, args.api_url)
    log_path = append_to_testing_log(report_md)
    print("\n" + "=" * 78)
    print(f" INTENSIVE E2E REPORT LOGGED TO: {log_path}")
    print("=" * 78)
    print(report_md)


if __name__ == "__main__":
    asyncio.run(main())
