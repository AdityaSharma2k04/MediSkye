"""
Production-fidelity mobile verification screenshot capture for Aarav Verma at 390px x 844px (deviceScaleFactor: 2).
Uses in-process Python SPA server serving frontend/dist and Playwright with network interception.
"""

import os
import sys
import time
import json
import base64
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("docs/screenshots/mobile_390px")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Generate valid JWT token for ProtectedRoute
header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
payload_dict = {
    "sub": "11111111-2222-3333-4444-555555555555",
    "email": "aarav.verma@example.com",
    "exp": 2500000000,
}
payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
MOCK_JWT = f"{header}.{payload}.mock_valid_signature_for_testing"

# Aarav Verma Mock Data
USER_PROFILE = {
    "id": "11111111-2222-3333-4444-555555555555",
    "email": "aarav.verma@example.com",
    "full_name": "Aarav Verma",
    "date_of_birth": "1997-04-12",
    "biological_sex": "Male",
    "blood_type": "B+",
    "weight_kg": 68.0,
    "height_cm": 175.0,
    "diet_type": "Vegetarian",
    "activity_level": "High (Sprint/Resistance)",
    "pre_existing_conditions": "Mild Asthma, Strict Lactose Intolerance",
    "current_medications": "Creatine Monohydrate 5g/d, Cholecalciferol 1000 IU/d, Levosalbutamol PRN",
    "known_allergies": "Penicillin, Sulfonamides, Ibuprofen (NSAIDs)",
    "language_preference": "English",
    "memory_consent_granted": True,
}

DOCUMENTS = [
    {
        "id": "22222222-0000-0000-0000-000000000001",
        "filename": "6-Month Follow-Up Laboratory Report - Aarav Verma.pdf",
        "title": "6-Month Follow-Up Laboratory Report",
        "collected_at": "24 Apr 2027",
        "is_future_collection_date": True,
        "created_at": "2026-11-06T12:00:00Z",
    },
    {
        "id": "22222222-0000-0000-0000-000000000002",
        "filename": "Comprehensive Laboratory Report - Aarav Verma.pdf",
        "title": "Baseline Comprehensive Laboratory Report",
        "collected_at": "24 Oct 2026",
        "is_future_collection_date": False,
        "created_at": "2026-11-06T10:00:00Z",
    },
]

METRICS_RESPONSE = {
    "document_id": "22222222-0000-0000-0000-000000000001",
    "collected_at": "24 Apr 2027",
    "is_future_collection_date": True,
    "prior_document_id": "22222222-0000-0000-0000-000000000002",
    "prior_document_date": "24 Oct 2026",
    "metrics": [
        {
            "test": "Serum Ferritin",
            "value": "24.0",
            "unit": "ng/mL",
            "range": "30.0 – 400.0",
            "status": "Low",
            "previous_value": "44.0",
            "previous_date": "24 Oct 2026",
            "delta_abs": "-20.0 ng/mL",
            "delta_pct": -45.5,
        },
        {
            "test": "Vitamin B12",
            "value": "176",
            "unit": "pg/mL",
            "range": "200 – 900",
            "status": "Low",
            "previous_value": "238",
            "previous_date": "24 Oct 2026",
            "delta_abs": "-62 pg/mL",
            "delta_pct": -26.1,
        },
        {
            "test": "Hemoglobin",
            "value": "13.6",
            "unit": "g/dL",
            "range": "13.0 – 17.0",
            "status": "Normal",
            "previous_value": "15.4",
            "previous_date": "24 Oct 2026",
            "delta_abs": "-1.8 g/dL",
            "delta_pct": -11.7,
            "delta_alert": "Notable Drop (-11.7%)",
        },
        {
            "test": "Serum Creatinine",
            "value": "1.29",
            "unit": "mg/dL",
            "range": "0.70 – 1.25",
            "status": "High",
            "previous_value": "1.22",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+0.07 mg/dL",
            "delta_pct": 5.7,
        },
        {
            "test": "AST (SGOT)",
            "value": "48",
            "unit": "U/L",
            "range": "10 – 40",
            "status": "High",
            "previous_value": "31",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+17 U/L",
            "delta_pct": 54.8,
        },
        {
            "test": "Serum Uric Acid",
            "value": "7.6",
            "unit": "mg/dL",
            "range": "3.5 – 7.2",
            "status": "High",
            "previous_value": "5.8",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+1.8 mg/dL",
            "delta_pct": 31.0,
        },
        {
            "test": "25-OH Vitamin D",
            "value": "46.0",
            "unit": "ng/mL",
            "range": "30.0 – 100.0",
            "status": "Normal",
            "previous_value": "34.5",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+11.5 ng/mL",
            "delta_pct": 33.3,
        },
        {
            "test": "ALT (SGPT)",
            "value": "34",
            "unit": "U/L",
            "range": "10 – 45",
            "status": "Normal",
            "previous_value": "28",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+6 U/L",
            "delta_pct": 21.4,
        },
        {
            "test": "Fasting Blood Glucose",
            "value": "92",
            "unit": "mg/dL",
            "range": "70 – 99",
            "status": "Normal",
            "previous_value": "88",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+4 mg/dL",
            "delta_pct": 4.5,
        },
        {
            "test": "HbA1c",
            "value": "5.2",
            "unit": "%",
            "range": "4.0 – 5.6",
            "status": "Normal",
            "previous_value": "5.1",
            "previous_date": "24 Oct 2026",
            "delta_abs": "+0.1%",
            "delta_pct": 2.0,
        },
    ],
}

FACTS_RESPONSE = [
    {
        "id": "f1",
        "category": "allergies",
        "fact_key": "Drug Allergies",
        "fact_value": "Penicillin, Sulfonamides, Ibuprofen (NSAIDs)",
        "created_at": "24 Oct 2026",
    },
    {
        "id": "f2",
        "category": "lifestyle",
        "fact_key": "Diet & Training",
        "fact_value": "Vegetarian, Competitive sprint training 4x/week",
        "created_at": "24 Oct 2026",
    },
    {
        "id": "f3",
        "category": "medications",
        "fact_key": "Supplements",
        "fact_value": "Creatine Monohydrate 5g daily, Vitamin D3 1000 IU daily",
        "created_at": "24 Apr 2027",
    },
]

COMPARISON_CHAT_TEXT = """### 🟡 The Short Version
Comparing your **24 Apr 2027 Follow-Up** with your **24 Oct 2026 Baseline**, your **25-OH Vitamin D** significantly improved (+33.3%, rising from 34.5 to 46.0 ng/mL into the normal range). However, several parameters worsened: **Serum Ferritin** and **Vitamin B12** dropped into deficient ranges (flagged Low), while **Serum Creatinine**, **AST (SGOT)**, and **Serum Uric Acid** moderately increased above reference bounds. In addition, your **Hemoglobin** experienced a notable drop (-11.7%) within the normal range.

*Comparing Baseline (24 Oct 2026) vs. Follow-Up (24 Apr 2027)*

| Biomarker | Oct 2026 (Baseline) | Apr 2027 (Follow-Up) | Change (Δ %) | Reference Range | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Serum Ferritin** | 44.0 ng/mL | 24.0 ng/mL | ↓ 20.0 ng/mL (-45.5%) | 30.0 – 400.0 ng/mL | ↓ Low |
| **Vitamin B12** | 238 pg/mL | 176 pg/mL | ↓ 62 pg/mL (-26.1%) | 200 – 900 pg/mL | ↓ Low |
| **Serum Creatinine** | 1.22 mg/dL | 1.29 mg/dL | ↑ 0.07 mg/dL (+5.7%) | 0.70 – 1.25 mg/dL | ↑ High |
| **AST (SGOT)** | 31 U/L | 48 U/L | ↑ 17 U/L (+54.8%) | 10 – 40 U/L | ↑ High |
| **Serum Uric Acid** | 5.8 mg/dL | 7.6 mg/dL | ↑ 1.8 mg/dL (+31.0%) | 3.5 – 7.2 mg/dL | ↑ High |
| **Hemoglobin** | 15.4 g/dL | 13.6 g/dL | ↓ 1.8 g/dL (-11.7%) | 13.0 – 17.0 g/dL | ↘ Notable Drop |
| **25-OH Vitamin D** | 34.5 ng/mL | 46.0 ng/mL | ↑ 11.5 ng/mL (+33.3%) | 30.0 – 100.0 ng/mL | ✓ Improved |
| **ALT (SGPT)** | 28 U/L | 34 U/L | ↑ 6 U/L (+21.4%) | 10 – 45 U/L | ✓ Normal |

### Key Clinical Insights & Confirmatory Workup
- **Renal Filtration & Creatine:** Your eGFR was calculated from Serum Creatinine, which is influenced by your daily 5g creatine monohydrate supplementation. A **Serum Cystatin C** test provides a muscle-mass-independent assessment.
- **AST Elevation (+54.8%):** With a normal ALT (34 U/L), isolated AST elevation may reflect skeletal muscle strain from sprint workouts. Checking **Creatine Kinase (CK)** and GGT after 48–72h of rest will differentiate muscle strain from hepatic origin.
- **Iron Depletion:** The 1.8 g/dL drop in Hemoglobin alongside depleted Ferritin (24 ng/mL) warrants physician evaluation and an iron panel (**TSAT, Serum Iron, TIBC**).
- **Dietary Adjustments:** Focus on iron-rich South Asian vegetarian staples (moong dal, rajma, kala chana, amaranth) paired with Vitamin C (lemon/amla). Standardize laboratory re-test window to **8–12 weeks**.
"""

CHAT_HISTORY = [
    {
        "id": "msg-1",
        "role": "user",
        "message": "Can you compare my latest follow-up lab report with my previous baseline?",
        "created_at": "2026-11-06T10:14:00Z",
    },
    {
        "id": "msg-2",
        "role": "ai",
        "message": COMPARISON_CHAT_TEXT,
        "created_at": "2026-11-06T10:15:00Z",
    },
]


class SPAHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="frontend/dist", **kwargs)

    def do_GET(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) or os.path.isdir(path):
            self.path = "/index.html"
        return super().do_GET()


def run_capture():
    PORT = 4173
    print(f"Starting Python SPA HTTP server on port {PORT}...")
    server = HTTPServer(("127.0.0.1", PORT), SPAHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with sync_playwright() as p:
            print("Launching Chromium with viewport 390x844 (deviceScaleFactor: 2)...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )

            # Pre-populate localStorage with valid JWT and closed sidebar on mobile
            init_script = f"""
            localStorage.setItem('token', '{MOCK_JWT}');
            localStorage.setItem('mediskye_user_email', 'aarav.verma@example.com');
            localStorage.setItem('mediskye_theme', 'dark');
            localStorage.setItem('mediskye_sidebar_open', 'false');
            """
            context.add_init_script(init_script)

            def handle_route(route):
                url = route.request.url
                # Check /chats first so /users/me/documents/{id}/chats is routed to CHAT_HISTORY
                if "/chats" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(CHAT_HISTORY),
                    )
                elif "/users/me/export-data" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({
                            "export_date": "2026-11-06",
                            "user": USER_PROFILE,
                            "documents": DOCUMENTS,
                            "facts": FACTS_RESPONSE,
                        }),
                    )
                elif "/extract-metrics" in url or "/metrics" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(METRICS_RESPONSE),
                    )
                elif "/users/me/documents" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(DOCUMENTS),
                    )
                elif "/users/me/facts" in url or "/memory/facts" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(FACTS_RESPONSE),
                    )
                elif "/memory/status" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps({"memory_consent_granted": True, "fact_count": len(FACTS_RESPONSE)}),
                    )
                elif "/users/me" in url or "/auth/me" in url or "/profile" in url:
                    route.fulfill(
                        status=200,
                        content_type="application/json",
                        body=json.dumps(USER_PROFILE),
                    )
                elif "/dependents" in url:
                    route.fulfill(status=200, content_type="application/json", body="[]")
                else:
                    route.continue_()

            context.route("http://localhost:8000/**", handle_route)

            page = context.new_page()
            page.add_init_script("document.documentElement.classList.add('dark');")

            print("Navigating to http://127.0.0.1:4173/chat...")
            page.goto("http://127.0.0.1:4173/chat", wait_until="networkidle")
            page.wait_for_timeout(2500)

            # Ensure dark mode is active
            page.evaluate("document.documentElement.classList.add('dark');")

            # Verify chat content is loaded
            print("Title:", page.title())
            body_text = page.locator("body").inner_text()
            print("Body snippet:", repr(body_text[:120]))

            # -------------------------------------------------------------
            # Screenshot 1: 1_mobile_390px_comparison_table.png
            # -------------------------------------------------------------
            print("Capturing 1_mobile_390px_comparison_table.png...")
            # Scroll table card so it sits cleanly below the top header and subheader
            page.evaluate("""() => {
                const tableCard = document.querySelector('.chat-messages-container div[class*="sm:hidden"]') || 
                                  document.querySelector('.overflow-x-auto') || 
                                  document.querySelector('table');
                if (tableCard) {
                    const header = document.querySelector('header');
                    const headerHeight = header ? header.offsetHeight : 56;
                    const subHeader = document.querySelector('[class*="sm:hidden"]');
                    const subHeight = subHeader ? subHeader.offsetHeight : 44;
                    const container = document.querySelector('.chat-messages-container');
                    if (container) {
                        const cardTop = tableCard.getBoundingClientRect().top;
                        const containerTop = container.getBoundingClientRect().top;
                        const scrollDiff = cardTop - containerTop - headerHeight - subHeight - 6;
                        container.scrollTop += scrollDiff;
                    } else {
                        tableCard.scrollIntoView({ block: 'start' });
                    }
                }
            }""")
            page.wait_for_timeout(600)

            p1 = OUTPUT_DIR / "1_mobile_390px_comparison_table.png"
            page.screenshot(path=str(p1), full_page=False)
            print(f"Captured {p1.name} ({p1.stat().st_size} bytes)")

            # -------------------------------------------------------------
            # Screenshot 2: 2_mobile_390px_lab_metrics.png
            # -------------------------------------------------------------
            print("Switching to Lab Metrics view...")
            metrics_btn = page.locator("button[aria-label='View extracted lab metrics table']:visible")
            if metrics_btn.count() > 0:
                metrics_btn.first.click()
                page.wait_for_timeout(1500)

            p2 = OUTPUT_DIR / "2_mobile_390px_lab_metrics.png"
            page.screenshot(path=str(p2), full_page=False)
            print(f"Captured {p2.name} ({p2.stat().st_size} bytes)")

            # -------------------------------------------------------------
            # Screenshot 3: 3_mobile_390px_settings_modal.png
            # -------------------------------------------------------------
            print("Opening Settings modal...")
            # Switch back to chat first
            chat_btn = page.locator("button[aria-label='Switch to chat view']:visible")
            if chat_btn.count() > 0:
                chat_btn.first.click()
                page.wait_for_timeout(500)

            # Open sidebar
            toggle_btn = page.locator("button[aria-label='Toggle sidebar']")
            if toggle_btn.count() > 0:
                toggle_btn.first.click(force=True)
                page.wait_for_timeout(600)

            settings_btn = page.locator("button:has-text('Settings')")
            if settings_btn.count() > 0:
                settings_btn.first.click(force=True)
                page.wait_for_timeout(1000)

            # Scroll settings modal to show Remembered Facts (unclipped) and Data & Privacy
            modal_body = page.locator(".settings-modal-body, div[role='dialog'] div.overflow-y-auto")
            if modal_body.count() > 0:
                modal_body.first.evaluate("el => el.scrollTo(0, 440);")
                page.wait_for_timeout(500)

            p3 = OUTPUT_DIR / "3_mobile_390px_settings_modal.png"
            page.screenshot(path=str(p3), full_page=False)
            print(f"Captured {p3.name} ({p3.stat().st_size} bytes)")

            # -------------------------------------------------------------
            # Screenshot 4: 4_mobile_390px_header_and_composer.png
            # -------------------------------------------------------------
            print("Capturing header and composer...")
            close_settings = page.locator("button[aria-label='Close settings']")
            if close_settings.count() > 0:
                close_settings.first.click(force=True)
                page.wait_for_timeout(600)

            # Ensure sidebar is closed on mobile
            page.evaluate("""() => {
                const aside = document.querySelector('aside');
                const backdrop = document.querySelector('[data-testid="sidebar-backdrop"]');
                if (backdrop) backdrop.click();
            }""")
            page.wait_for_timeout(500)

            # Scroll to top of chat
            page.evaluate("document.querySelector('.chat-messages-container')?.scrollTo(0, 0);")
            page.wait_for_timeout(500)

            p4 = OUTPUT_DIR / "4_mobile_390px_header_and_composer.png"
            page.screenshot(path=str(p4), full_page=False)
            print(f"Captured {p4.name} ({p4.stat().st_size} bytes)")

            browser.close()
            print("All 4 mobile screenshots captured successfully!")

    finally:
        server.shutdown()


if __name__ == "__main__":
    run_capture()
