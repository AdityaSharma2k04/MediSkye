"""
Production-fidelity visual verification script for MediSkye Clinical Obsidian Redesign.
Captures:
  1. Desktop (1440x900): Split-Pane Workbench with Chat on left & InspectorPanel Overview on right
  2. Desktop (1440x900): Command Palette (Ctrl+K) open over Workbench
  3. Mobile (390x844 @2x): Mobile LabMetrics biomarker cards with RangeBar & DeltaIndicator
  4. Mobile (390x844 @2x): Mobile Insights / Trends view (Longitudinal Trend Charts)
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

OUTPUT_DIR = Path("docs/screenshots/redesign")
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

TRENDS_RESPONSE = {
    "patient_id": "self",
    "generated_at": "2026-11-07T08:30:00Z",
    "reports": [
        {
            "document_id": "22222222-0000-0000-0000-000000000002",
            "title": "Baseline Comprehensive Laboratory Report",
            "collected_at": "24 Oct 2026",
        },
        {
            "document_id": "22222222-0000-0000-0000-000000000001",
            "title": "6-Month Follow-Up Laboratory Report",
            "collected_at": "24 Apr 2027",
        },
    ],
    "series": [
        {
            "key": "serum_ferritin",
            "name": "Serum Ferritin",
            "unit": "ng/mL",
            "reference_range": "30.0 – 400.0",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 44.0,
                    "raw_value": "44.0",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 24.0,
                    "raw_value": "24.0",
                    "status": "Low",
                },
            ],
        },
        {
            "key": "vitamin_b12",
            "name": "Vitamin B12",
            "unit": "pg/mL",
            "reference_range": "200 – 900",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 238.0,
                    "raw_value": "238",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 176.0,
                    "raw_value": "176",
                    "status": "Low",
                },
            ],
        },
        {
            "key": "hemoglobin",
            "name": "Hemoglobin",
            "unit": "g/dL",
            "reference_range": "13.0 – 17.0",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 15.4,
                    "raw_value": "15.4",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 13.6,
                    "raw_value": "13.6",
                    "status": "Normal",
                },
            ],
        },
        {
            "key": "serum_creatinine",
            "name": "Serum Creatinine",
            "unit": "mg/dL",
            "reference_range": "0.70 – 1.25",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 1.22,
                    "raw_value": "1.22",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 1.29,
                    "raw_value": "1.29",
                    "status": "High",
                },
            ],
        },
        {
            "key": "ast_sgot",
            "name": "AST (SGOT)",
            "unit": "U/L",
            "reference_range": "10 – 40",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 31.0,
                    "raw_value": "31",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 48.0,
                    "raw_value": "48",
                    "status": "High",
                },
            ],
        },
        {
            "key": "25_oh_vitamin_d",
            "name": "25-OH Vitamin D",
            "unit": "ng/mL",
            "reference_range": "30.0 – 100.0",
            "points": [
                {
                    "document_id": "22222222-0000-0000-0000-000000000002",
                    "collected_at": "24 Oct 2026",
                    "value": 34.5,
                    "raw_value": "34.5",
                    "status": "Normal",
                },
                {
                    "document_id": "22222222-0000-0000-0000-000000000001",
                    "collected_at": "24 Apr 2027",
                    "value": 46.0,
                    "raw_value": "46.0",
                    "status": "Normal",
                },
            ],
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
        "source_document_id": "22222222-0000-0000-0000-000000000002",
    },
    {
        "id": "f2",
        "category": "lifestyle",
        "fact_key": "Diet & Training",
        "fact_value": "Vegetarian, Competitive sprint training 4x/week",
        "created_at": "24 Oct 2026",
        "source_document_id": "22222222-0000-0000-0000-000000000002",
    },
    {
        "id": "f3",
        "category": "medications",
        "fact_key": "Supplements",
        "fact_value": "Creatine Monohydrate 5g daily, Vitamin D3 1000 IU daily",
        "created_at": "24 Apr 2027",
        "source_document_id": "22222222-0000-0000-0000-000000000001",
    },
]

COMPARISON_CHAT_TEXT = """### 🟡 Clinical Summary & Longitudinal Comparison
Comparing your **24 Apr 2027 Follow-Up** with your **24 Oct 2026 Baseline**, your **25-OH Vitamin D** significantly improved (+33.3%, rising from 34.5 to 46.0 ng/mL into the optimal normal range). However, several parameters shifted: **Serum Ferritin** and **Vitamin B12** dropped into deficient ranges (flagged Low), while **Serum Creatinine**, **AST (SGOT)**, and **Serum Uric Acid** moderately increased above reference bounds. In addition, your **Hemoglobin** experienced a notable drop (-11.7%) within the normal range.

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


def handle_api_route(route):
    url = route.request.url
    if "/users/me/metrics/trends" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(TRENDS_RESPONSE))
    elif "/users/me/dependents" in url:
        route.fulfill(status=200, content_type="application/json", body="[]")
    elif "/users/me/documents" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(DOCUMENTS))
    elif "/chats" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(CHAT_HISTORY))
    elif "/extract-metrics" in url or "/metrics" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(METRICS_RESPONSE))
    elif "/users/me/facts" in url or "/memory/facts" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(FACTS_RESPONSE))
    elif "/memory/status" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"memory_consent_granted": True, "fact_count": len(FACTS_RESPONSE)}))
    elif "/users/me" in url or "/auth/me" in url or "/profile" in url:
        route.fulfill(status=200, content_type="application/json", body=json.dumps(USER_PROFILE))
    else:
        route.fulfill(status=200, content_type="application/json", body="{}")


def run_capture():
    PORT = 4173
    print(f"Starting Python SPA HTTP server on port {PORT}...")
    server = HTTPServer(("127.0.0.1", PORT), SPAHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ─────────────────────────────────────────────────────────────
            # 1. Desktop Browser Context (1440 x 900)
            # ─────────────────────────────────────────────────────────────
            print("Launching Desktop Chromium at 1440x900...")
            desktop_context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )

            desktop_init = f"""
            localStorage.setItem('token', '{MOCK_JWT}');
            localStorage.setItem('mediskye_user_email', 'aarav.verma@example.com');
            localStorage.setItem('mediskye_theme', 'dark');
            localStorage.setItem('mediskye_sidebar_open', 'true');
            localStorage.setItem('mediskye_inspector_open', 'true');
            localStorage.setItem('mediskye_inspector_tab', 'overview');
            """
            desktop_context.add_init_script(desktop_init)
            desktop_context.route("http://localhost:8000/**", handle_api_route)

            desktop_page = desktop_context.new_page()
            desktop_page.add_init_script("document.documentElement.classList.add('dark');")

            print("Navigating desktop to http://127.0.0.1:4173/chat...")
            desktop_page.goto("http://127.0.0.1:4173/chat", wait_until="networkidle")
            desktop_page.wait_for_timeout(2500)
            desktop_page.evaluate("document.documentElement.classList.add('dark');")

            # ── Screenshot 1: Desktop Split-Pane Workbench ──
            print("Capturing 1_desktop_workbench_split_pane.png (1440x900)...")
            p1 = OUTPUT_DIR / "1_desktop_workbench_split_pane.png"
            desktop_page.screenshot(path=str(p1), full_page=False)
            print(f"Captured {p1.name} ({p1.stat().st_size} bytes)")

            # ── Screenshot 2: Desktop Command Palette (Ctrl+K) ──
            print("Opening Command Palette with search button / Ctrl+K...")
            search_btn = desktop_page.locator("button[aria-label='Open command palette']").first
            if search_btn.count() > 0:
                search_btn.click()
            else:
                desktop_page.keyboard.press("Control+k")

            desktop_page.wait_for_timeout(1000)
            p2 = OUTPUT_DIR / "2_desktop_command_palette.png"
            desktop_page.screenshot(path=str(p2), full_page=False)
            print(f"Captured {p2.name} ({p2.stat().st_size} bytes)")

            desktop_context.close()

            # ─────────────────────────────────────────────────────────────
            # 2. Mobile Browser Context (390 x 844 @ 2x)
            # ─────────────────────────────────────────────────────────────
            print("Launching Mobile Chromium at 390x844 (deviceScaleFactor: 2)...")
            mobile_context = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )

            mobile_init = f"""
            localStorage.setItem('token', '{MOCK_JWT}');
            localStorage.setItem('mediskye_user_email', 'aarav.verma@example.com');
            localStorage.setItem('mediskye_theme', 'dark');
            localStorage.setItem('mediskye_sidebar_open', 'false');
            """
            mobile_context.add_init_script(mobile_init)
            mobile_context.route("http://localhost:8000/**", handle_api_route)

            mobile_page = mobile_context.new_page()
            mobile_page.add_init_script("document.documentElement.classList.add('dark');")

            print("Navigating mobile to http://127.0.0.1:4173/chat...")
            mobile_page.goto("http://127.0.0.1:4173/chat", wait_until="networkidle")
            mobile_page.wait_for_timeout(2500)
            mobile_page.evaluate("document.documentElement.classList.add('dark');")

            # ── Screenshot 3: Mobile Lab Metrics Cards with RangeBar ──
            print("Switching to Mobile Lab Metrics view...")
            metrics_tab = mobile_page.locator("button[aria-label='View extracted lab metrics table']:visible")
            if metrics_tab.count() > 0:
                metrics_tab.first.click()
                mobile_page.wait_for_timeout(1500)

            p3 = OUTPUT_DIR / "3_mobile_lab_metrics_cards.png"
            mobile_page.screenshot(path=str(p3), full_page=False)
            print(f"Captured {p3.name} ({p3.stat().st_size} bytes)")

            # ── Screenshot 4: Mobile Insights / Trends View ──
            print("Switching to Mobile Insights / Trends view...")
            insights_tab = mobile_page.locator("button[aria-label='View clinical insights and trends']:visible")
            if insights_tab.count() > 0:
                insights_tab.first.click()
                mobile_page.wait_for_timeout(1000)

            # Click Trends tab in inspector to show longitudinal graphs
            trends_tab_btn = mobile_page.locator("button[role='tab']:has-text('Trends')")
            if trends_tab_btn.count() > 0:
                trends_tab_btn.first.click()
                mobile_page.wait_for_timeout(1500)

            p4 = OUTPUT_DIR / "4_mobile_insights_trends.png"
            mobile_page.screenshot(path=str(p4), full_page=False)
            print(f"Captured {p4.name} ({p4.stat().st_size} bytes)")

            mobile_context.close()
            browser.close()

            print("All screenshots captured successfully in docs/screenshots/redesign!")

    finally:
        print("Shutting down SPA server...")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run_capture()
