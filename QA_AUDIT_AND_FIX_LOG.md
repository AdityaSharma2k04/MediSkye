# 🕵️‍♂️ MediSkye: Full-Codebase Autonomous QA Audit & Fix Log

**Date:** November 14, 2026  
**Auditor:** Principal Staff Engineer & Simulated Human QA Tester  
**Repository Scope:** `backend/app/`, `frontend/src/`, `frontend/src-tauri/`, `frontend/android/`  
**Test Deliverables:**  
- `frontend/src/test/HumanQASimulation.test.jsx` (4 multi-step simulated user journeys)
- `backend/tests/test_qa_user_journeys.py` (7 multi-turn, security, and clinical parsing tests)
- `backend/tests/test_qa_parsing.py` (De-overfitting and unit normalization test suite)

---

## 📊 Summary of Audit Findings & Status

| ID | Title | Category | Severity | Status |
|---|---|---|---|---|
| **QA-01** | Number & Indian Lakhs Notation Parsing Flaw Causes False Critical Thrombocytopenia Alarms | `Overfitting` | Critical | **FIXED & VERIFIED** |
| **QA-02** | Urinalysis vs. Serum Albumin Lookahead Collision Triggers False Hypoalbuminemia Panic | `RAG/Prompt Pipeline` | Critical | **FIXED & VERIFIED** |
| **QA-03** | Brittle Overview Regex Locks Users in Narrow Follow-Up Mode on Turn 2+ | `Overfitting` | High | **FIXED & VERIFIED** |
| **QA-04** | Trailing Code Fences & Internal System Prompt XML Tags Leak During Real-Time Streaming | `State/UX Glitch` | High | **FIXED & VERIFIED** |
| **QA-05** | Cross-Device Deletion Resurrection Bug in Cloud Sync (`ChatApp.jsx`) | `Sync/Offline Bug` | High | **FIXED & VERIFIED** |
| **QA-06** | Mid-Stream Profile Switch / Chat Switch Race Condition & Cache Bleed | `State/UX Glitch` | High | **FIXED & VERIFIED** |
| **QA-07** | Upload Failure / Polling Timeout Leaves Profile Switcher Stuck Locked | `State/UX Glitch` | Medium | **FIXED & VERIFIED** |
| **QA-08** | Android `pendingAuthIdToken` Replay Causes Unexpected Re-Login on App Resume After Logout | `Auth/Native Shell` | High | **FIXED & VERIFIED** |
| **QA-09** | Normal Near-Boundary Biomarkers Counted as Out-of-Range in Lab Metrics Header Badge | `Memory/Metrics/Trends` | Medium | **FIXED & VERIFIED** |
| **QA-10** | Premature Blob URL Revocation in `ExportModal` Causes Aborted Downloads in WebViews | `State/UX Glitch` | Medium | **FIXED & VERIFIED** |
| **QA-11** | Longitudinal Trends Render `NaN` Points on Comparators & Number Notations | `Memory/Metrics/Trends` | Medium | **FIXED & VERIFIED** |
| **QA-12** | Unhandled Rejection & Missing Cache Functions on Manual Cloud Sync in `ChatApp` | `State/UX Glitch` | Medium | **FIXED & VERIFIED** |

---

## 🔍 Detailed Audit & Fix Records

### QA-01: Number & Indian Lakhs Notation Parsing Flaw Causes False Critical Thrombocytopenia Alarms
- **Category:** `Overfitting`
- **What Was Broken (Symptom):**  
  When a patient uploaded an Indian or international lab report containing numbers formatted with commas (such as `2,38,000` platelets or `4,500.50` WBC), the system parsed the value as `2.0` and `4.0`. This triggered false critical alerts for life-threatening thrombocytopenia, panicking healthy patients.
- **Root Cause & File/Line Location:**  
  `backend/app/rag/biomarkers.py` and `backend/app/services/clinical_units.py`: The regular expression `^\d{1,3}(,\d{3})+(?!\.\d+)$` strictly checked for standard 3-digit comma groups without decimal points. It completely failed on Indian 2-digit groups (`2,38,000`) and standard thousands with decimals (`4,500.50`), causing regex fallback that extracted only the leading digit.
- **The Fix & Code Changes:**  
  Added `_normalize_numeric_string()` in `biomarkers.py` and `clinical_units.py`:
  1. Strips leading comparators (`<`, `>`, `<=`, `>=`).
  2. Detects Indian numbering format (`\d{1,2}(?:,\d{2})*,\d{3}`) and thousands with decimals (`\d{1,3}(?:,\d{3})+(?:\.\d+)?`), stripping commas so Python parses `238000.0` and `4500.5`.
  3. Handles European decimal commas (e.g. `3,9` $\to$ `3.9`).
- **Verification Proof:**  
  `backend/tests/test_qa_parsing.py::test_numeric_parsing_diverse_formats`  
  `backend/tests/test_qa_user_journeys.py::test_numeric_parsing_indian_and_thousands_notations`

---

### QA-02: Urinalysis vs. Serum Albumin Lookahead Collision Triggers False Hypoalbuminemia Panic
- **Category:** `RAG/Prompt Pipeline`
- **What Was Broken (Symptom):**  
  A patient uploading a routine urinalysis report containing "Urine Albumin: 30 mg/L" received alarming warnings about severe liver/kidney disease and hypoalbuminemia because the app mapped it to Serum Albumin (healthy range 3.5 - 5.0 g/dL).
- **Root Cause & File/Line Location:**  
  `backend/app/rag/biomarkers.py` and `backend/app/services/clinical_units.py`: Rule 0b regex `urine(?!\s*acr|\s*albumin)` explicitly excluded `urine albumin` from urinalysis categorization, allowing it to drop into Rule 7 which mapped "albumin" to serum albumin.
- **The Fix & Code Changes:**  
  Updated Rule 0b lookahead to `urine(?!\s*acr|\s*albumin\s*(?:to|/)?\s*creatinine)|microalbumin` so urine albumin/microalbumin is classified as urinalysis, not serum albumin. Added canonical keys `albumin`, `globulin`, `total_protein`.
- **Verification Proof:**  
  `backend/tests/test_qa_parsing.py::test_urinalysis_vs_serum_albumin`  
  `backend/tests/test_qa_user_journeys.py::test_urinalysis_vs_serum_albumin_disambiguation`

---

### QA-03: Brittle Overview Regex Locks Users in Narrow Follow-Up Mode on Turn 2+
- **Category:** `Overfitting`
- **What Was Broken (Symptom):**  
  If a user asked a specific question first (Turn 1: *"What is my HbA1c?"*) and then on Turn 2 asked *"Now give me the full overview of this report"* or *"walk me through the whole report"*, the assistant refused to provide the walkthrough and gave a 2-line follow-up answer.
- **Root Cause & File/Line Location:**  
  `backend/app/api/v1/endpoints/query.py`: `explicit_overview_match` regex was rigidly anchored with `r"^(give\s+me|tell\s+me\s+about|walk\s+me\s+through)..."`, failing on conversational prefixes (`Now`, `Please`, `Can you`), variations (`the whole report`, `entire report`), or standalone requests (`full overview`).
- **The Fix & Code Changes:**  
  Generalized `explicit_overview_match` with optional polite/conversational prefixes, synonyms, and boundary detection:
  ```python
  r"(?i)(?:^(?:now\s+)?(?:can\s+you\s+)?(?:give\s+me\s+)?(?:the\s+|a\s+)?(?:full|complete|entire)\s+(?:overview|breakdown|summary)(?:\s+of\s+(?:this|my|the)?\s*(?:report|results?|blood\s*work)?)?|\b(?:tell\s+me\s+about|explain|summarize|walk\s+me\s+through|give\s+me\s+(?:a|the)?\s*(?:full|complete|entire)?\s*(?:overview|breakdown|summary)\s*(?:of)?|(?:full|complete|entire)\s+(?:overview|breakdown|summary)\s*(?:of)?|overview\s+of)\s+(?:this|my|the|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|results?))\b"
  ```
- **Verification Proof:**  
  `backend/tests/test_qa_user_journeys.py::test_explicit_overview_regex_generalization`

---

### QA-04: Trailing Code Fences & Internal System Prompt XML Tags Leak During Real-Time Streaming
- **Category:** `State/UX Glitch`
- **What Was Broken (Symptom):**  
  While the AI streamed tokens in real time, users saw raw flashing ````json {"abnormal_flags": ...} ```` blocks or prompt XML tags (`<extracted_report_biomarkers>`, `<followup_turn_instruction>`) before the stream completed.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ChatMessage.jsx`: `stripAbnormalFlags` only handled completed code fences with strict language tags and rigid XML tags without attributes or whitespace.
- **The Fix & Code Changes:**  
  Expanded `stripAbnormalFlags()` in `ChatMessage.jsx`:
  1. Strips open/partial code fences during live streaming: `/(?:```|~~~)(?:json)?\s*\{[\s\S]*?"abnormal_flags"[\s\S]*$/gi`.
  2. Strips XML tags with attributes (`<extracted_report_biomarkers count="2">`) and self-closing tags (`<tag />`).
- **Verification Proof:**  
  `frontend/src/test/HumanQASimulation.test.jsx::QA Journey 4 (Streaming JSON & Disclaimer Cleanliness)`

---

### QA-05: Cross-Device Deletion Resurrection Bug in Cloud Sync (`ChatApp.jsx`)
- **Category:** `Sync/Offline Bug`
- **What Was Broken (Symptom):**  
  If a user deleted a chat or report on their Laptop (deleting it from Neon DB) and tapped the Refresh/Sync button on their Android or second device, the deleted chat reappeared in the sidebar forever.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ChatApp.jsx`: `refreshDocuments()` merged local cached conversations (`localNonDocConvs`) without checking if non-draft conversations still existed on the server, resurrecting deleted chats.
- **The Fix & Code Changes:**  
  Made the server list authoritative when online and network succeeds, keeping local cached messages for existing docs while cleanly evicting deleted documents/sessions and preserving draft "New Chat":
  ```javascript
  if (networkSucceeded) {
    const validServerDocIds = new Set(effectiveDocs.map((d) => String(d.id)));
    const validServerSessionIds = new Set(
      Array.isArray(chatSessionsRes) ? chatSessionsRes.map((s) => String(s.session_id)) : []
    );
    // Remove obsolete non-draft conversations that no longer exist on the server
    setConversations((prev) => ...);
  }
  ```
- **Verification Proof:**  
  `frontend/src/test/HumanQASimulation.test.jsx::QA Journey 2 (Cross-Device Cloud Sync & Deletion Reconciliation)`

---

### QA-06: Mid-Stream Profile Switch / Chat Switch Race Condition & Cache Bleed
- **Category:** `State/UX Glitch`
- **What Was Broken (Symptom):**  
  If a user switched profiles or clicked another chat while a response was streaming, the background stream could bleed tokens into the newly selected chat or corrupt the active patient's local storage.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ChatApp.jsx`: In `sendQueryStream` chunk callback, an early return `if (sessionIdRef.current !== activeTargetId) return;` dropped streaming tokens for background chats, and `setCachedConversations` used `localStorage.getItem('mediskye_patient_id')` instead of the originating `targetPatient`.
- **The Fix & Code Changes:**  
  Functional updater updates the specific `targetConvId` regardless of current active chat, and caching is strictly scoped to `targetPatient`.
- **Verification Proof:**  
  `frontend/src/test/HumanQASimulation.test.jsx::QA Journey 1 (Cold Launch & Profile Switch Bleed-Over)`

---

### QA-07: Upload Failure / Polling Timeout Leaves Profile Switcher Stuck Locked
- **Category:** `State/UX Glitch`
- **What Was Broken (Symptom):**  
  When an upload failed or timed out, the profile switcher remained locked with an amber lock icon, preventing the user from switching patient context on a broken empty chat.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ChatApp.jsx`: On upload errors/timeouts, `activePdf` and conversation PDF metadata were not consistently rolled back to null.
- **The Fix & Code Changes:**  
  Guaranteed `setActivePdf(null)` and conversation PDF/document cleanup in all error/timeout paths.
- **Verification Proof:**  
  `frontend/src/components/ChatApp.jsx` upload rollback handlers and `HumanQASimulation.test.jsx`.

---

### QA-08: Android `pendingAuthIdToken` Replay Causes Unexpected Re-Login on App Resume After Logout
- **Category:** `Auth/Native Shell`
- **What Was Broken (Symptom):**  
  When a user logged out inside the Android app and later minimized/resumed the app, `MainActivity.java` re-dispatched the old token, logging them back in without authorization.
- **Root Cause & File/Line Location:**  
  `frontend/android/app/src/main/java/com/mediskye/app/MainActivity.java`: `pendingAuthIdToken` and `pendingAuthAccessToken` remained in memory and were never nulled after dispatch.
- **The Fix & Code Changes:**  
  Reset `pendingAuthIdToken = null` and `pendingAuthAccessToken = null` immediately upon dispatch in `dispatchAuthTokensToWebView()` and `onResume()`, and added `clearPendingAuth()` to `MediskyeNativeBridge`.
- **Verification Proof:**  
  `frontend/android/app/src/main/java/com/mediskye/app/MainActivity.java` verified.

---

### QA-09: Normal Near-Boundary Biomarkers Counted as Out-of-Range in Lab Metrics Header Badge
- **Category:** `Memory/Metrics/Trends`
- **What Was Broken (Symptom):**  
  Lab Metrics header badge displayed "3 Out of Range" when backend only flagged 1 abnormal marker because near-boundary "high-normal" or "low-normal" markers were classified as abnormal.
- **Root Cause & File/Line Location:**  
  `frontend/src/lib/clinical.js`: `classifyStatus()` matched `'high-normal'` with `s.startsWith('high')` and `'low-normal'` with `s.startsWith('low')`, returning `'high'` / `'low'` instead of `'normal'`.
- **The Fix & Code Changes:**  
  Classified `'high-normal'` and `'low-normal'` as `'normal'` prior to prefix checks, and updated `parseNumeric()` to handle commas and comparators.
- **Verification Proof:**  
  `frontend/src/lib/clinical.js` unit parity with backend `status_summary`.

---

### QA-10: Premature Blob URL Revocation in `ExportModal` Causes Aborted Downloads in WebViews
- **Category:** `State/UX Glitch`
- **What Was Broken (Symptom):**  
  Exporting a summary or report in Windows WebView2 or Android WebView failed silently or aborted because `URL.revokeObjectURL(url)` ran synchronously before the native download started.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ExportModal.jsx`: Revoked the blob object URL immediately after `a.click()`.
- **The Fix & Code Changes:**  
  Deferred `URL.revokeObjectURL(url)` by 2000ms inside `setTimeout()`.
- **Verification Proof:**  
  `frontend/src/components/ExportModal.jsx` verified.

---

### QA-11: Longitudinal Trends Render `NaN` Points on Comparators & Number Notations
- **Category:** `Memory/Metrics/Trends`
- **What Was Broken (Symptom):**  
  Trend charts rendered broken `NaN` coordinates when biomarkers had `<`/`>` prefixes (e.g., `< 0.5`) or thousands notation (`2,38,000`).
- **Root Cause & File/Line Location:**  
  `frontend/src/hooks/useTrendData.js`: Used raw `parseFloat(p.value)` which failed on prefixes and comma groups.
- **The Fix & Code Changes:**  
  Replaced `parseFloat(p.value)` with `parseNumeric(p.value)`.
- **Verification Proof:**  
  `frontend/src/hooks/useTrendData.js` and `clinical.js` verified.

---

### QA-12: Unhandled Rejection & Missing Cache Functions on Manual Cloud Sync in `ChatApp`
- **Category:** `State/UX Glitch`
- **What Was Broken (Symptom):**  
  Tapping manual sync threw `TypeError: Cannot read properties of undefined (reading 'catch')` or `ReferenceError: setCachedProfile is not defined`.
- **Root Cause & File/Line Location:**  
  `frontend/src/components/ChatApp.jsx`: Missing imports for `setCachedProfile` / `setCachedDependents`, and unshielded `.catch()` calls on non-promise returns.
- **The Fix & Code Changes:**  
  Imported `setCachedProfile` and `setCachedDependents`, wrapped `Promise.resolve(...)` around dynamic calls.
- **Verification Proof:**  
  `frontend/src/test/HumanQASimulation.test.jsx::QA Journey 2`.
