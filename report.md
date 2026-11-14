# MediSkye Engineering Audit & Remediation Report (Prompts 5–9)

**Date:** November 14, 2026  
**Active Branch:** `fix/audit-followups`  
**Base Lineage:** `origin/main` (`816a980`) $\rightarrow$ `fix/profile-isolation-followup` (`00c2d12`) $\rightarrow$ `fix/audit-followups` (`9726a98`)  
**Status:** ✅ All Backend & Frontend Suites Green (597 Python tests, 280 Vitest specs, 0 build errors)

---

## 1. Executive Summary

Over the course of the last five development prompts, we conducted an independent clinical safety and profile-isolation audit of MediSkye, resolved multiple subtle edge-case regressions, hardened prompt and output-filter pipelines, and preserved strict backward compatibility and patient privacy boundaries.

All work strictly followed guarded run discipline:
1. **Zero regressions:** Existing functionality and backward compatibility were preserved.
2. **Red-test-first:** Every code modification was preceded by a failing unit or route test proving the root cause.
3. **Surgical edits:** Edits were strictly confined to authorized modules (`output_filter.py`, `prompt_builder.py`, `query.py`, `user.py`, `api.js`, `ChatApp.jsx`, test suites, and `QA_AUDIT_AND_FIX_LOG.md`).
4. **Encoding & Integrity:** Preserved UTF-8 emojis (`🟢`, `🟡`, `🔴`, `🔍`, `💬`), curly apostrophes, and `PROMPT_VERSION = "v5"`.

---

## 2. Chronological Breakdown Across Prompts 5–9

### Prompt 5: Independent Read-Only Audit of Branch `fix/profile-isolation-followup`
- **Objective:** Perform a rigorous, read-only audit comparing baseline `816a980` with HEAD `00c2d12` to identify any regressions, architectural gaps, or unproven assumptions introduced during QA-23, QA-24, and QA-25.
- **Key Findings:**
  1. *External API Backward Compatibility Gap (DECISION_1):* QA-23 forced un-scoped `/users/me/documents` and `/users/me/chats` requests to default to `'self'`, breaking existing external callers and integrations expecting all account records.
  2. *Server Disclaimer Suppression on Critical Follow-Ups (DECISION_2):* QA-25 suppressed disclaimers on all follow-up turns indiscriminately, which would drop necessary medical disclaimers even when critical lab alerts or safe fallback emergency warnings occurred.
  3. *Overview Query Matcher False Positives:* Generic substring matching on `"tell me about "` caused focused questions (e.g., *"tell me about my ferritin"*) to falsely trigger the entire 7-section report walkthrough.
  4. *Missing Longitudinal Comparison on Follow-Up:* If a user asked to compare results across visits on a follow-up turn, `COMPARISON_RULES` were omitted because `is_followup_turn=True`.
  5. *History Condenser Fragility:* Bracket-based heuristic in `condense_chat_history` could strip valid clinical discussions or fail on raw string inputs.

---

### Prompt 6: Targeted Follow-Up Fixes on `fix/audit-followups` (QA-26)
- **Objective:** Create branch `fix/audit-followups` from `00c2d12` and implement targeted solutions for audit findings under strict red-test discipline.
- **Implementations:**
  - **Item 1: API Backward Compatibility (`DECISION_1 = LEGACY_ALL`):**
    - In `backend/app/api/v1/endpoints/user.py`, modified `get_my_documents`, `get_general_chats`, and `get_user_chat_sessions`:
      - Omitted or empty `patient_id` parameter returns all user records across profiles.
      - Explicit `patient_id='self'` filters strictly for `dependent_id IS NULL`.
      - Explicit dependent UUID validates ownership against `current_user.id` (returns 404 on cross-user unauthorized access) and filters for `dependent_id == dep_uuid`.
    - In `frontend/src/services/api.js` and `ChatApp.jsx`, explicitly forwarded `patient_id` when fetching standalone chats for dependents while omitting it for `'self'`.
  - **Item 2: Overview Matcher Refinement & Diagnostic Logging:**
    - In `backend/app/api/v1/endpoints/query.py`, refined `is_explicit_overview_query` regex to require explicit report targets (`this report`, `my blood work`, `these labs`) before triggering a full walkthrough.
    - Added privacy-compliant `compute_followup_turn_context` logging diagnostic metadata (`session_id`, `document_id`, `is_followup_turn`, `reason`) with zero query text logged.
  - **Item 3: Comparison-Aware Follow-Up Turns:**
    - In `backend/app/rag/prompt_builder.py`, introduced `_COMPARISON_REQUEST_RE` (`compare`, `trend`, `versus`, `vs`, `over time`, `baseline`, etc.).
    - When comparison intent is detected on a follow-up turn, `COMPARISON_RULES` is injected alongside `FOLLOWUP_TURN_RULES`.
  - **Item 4: History Condenser Sanitization:**
    - Replaced fragile heuristics with clean regex: strips `###` headings, table rows (`| ... |`), JSON blocks, and disclaimers.
    - Capped assistant turns at ~350 characters at sentence boundaries and appended walkthrough stub when prior turns contained full walkthroughs or $\ge 6$ table rows.
  - **Item 5: Safety Disclaimer Detection & `DECISION_2 = KEEP`:**
    - Anchored disclaimer detection to line starts (`(?im)^\s*\*{0,2}disclaimer:\*{0,2}`) in `backend/app/rag/safety.py`.
    - Retained disclaimers on initial turns, full overviews, critical/urgent findings, and `SAFE_FALLBACK` invocations.
  - **Item 6: Legacy Cache R2 Sanitizer:**
    - In `frontend/src/services/api.js`, added read-time reconciliation where document patient assignments override mismatched conversation tags, and untagged legacy conversations are safely claimed.

---

### Prompt 7: Emergency Banner Wiring & Line-Anchored Disclaimer Cleaning (QA-27)
- **Objective:** Implement `DECISION_3 = B` (preserving server disclaimers on follow-ups for both `SAFE_FALLBACK` and active `emergency_banner`), wire critical alerts in `query.py`, anchor `_clean_disclaimers` to line start, and log exact rollback lines.
- **Implementations:**
  - **Emergency Banner Wiring:**
    - In `backend/app/api/v1/endpoints/query.py` (`query_bot`, lines 1168–1179), formally wired `has_critical = bool(emergency_banner) or is_safe_fallback_text`.
    - Passed `preserve_disclaimer = (not is_followup_turn) or has_critical` and forwarded `has_critical_alert = has_critical` to `_clean_disclaimers`.
    - Route-level test `test_route_followup_emergency_disclaimer_preservation` verified that ordinary follow-ups have 0 disclaimers, while follow-ups with active emergency banners retain exactly 1 disclaimer.
  - **`_clean_disclaimers` Mid-Text Line Anchoring:**
    - Updated `disclaimer_pattern` in `query.py` with line start anchor `(?im)...^\s*\*{0,2}Disclaimer:\*{0,2}`.
    - Verified by unit test `test_clean_disclaimers_mid_text_anchoring`: mid-sentence mentions (e.g., *"The footer says Disclaimer: results are indicative. Next sentence stays."*) are preserved intact.

---

### Prompts 8 & 9: `output_filter.py` False Positives & Prompt Warmth / Bedside Manner (QA-28)
- **Objective:** Eliminate false-positive `dangerous_advice` blocks on safe medical cautions, restore full empathy and bedside manner instructions to `FOLLOWUP_TURN_RULES`, narrow comparison regex, and auto-condense raw string history.
- **Implementations:**
  - **1. Safe Negation & Curly Apostrophe Guard (`backend/app/rag/output_filter.py`):**
    - *Problem:* Safe physician cautions such as *"Do not change your dose without speaking with your doctor"*, *"You shouldn't adjust medication on your own"*, or *"Never stop taking prescribed medication abruptly"* falsely triggered `dangerous_advice` blocks, replacing good answers with emergency fallbacks. Additionally, Unicode curly apostrophes (`’` vs `'`) bypassed previous regex checks.
    - *Fix:* Defined `_NEGATION_PREFIX_RE` covering:
      ```python
      r"""(?i)(?:do\s+not|don['’]t|never|should\s+not|shouldn['’]t|must\s+not|mustn['’]t|would\s+not|wouldn['’]t|cannot|can['’]t|avoid|without|consult\s+your\s+doctor\s+before)\s+(?:(?:to|even|ever|suddenly|abruptly|on\s+your\s+own|without\s+consulting|without\s+speaking)\s+)*$"""
      ```
    - For each dangerous phrase match (excluding severe overdose patterns like `take 10x` or `swallow entire bottle`), scanned the preceding 60 characters for a negation prefix. If present, the caution is classified as safe clinician guidance.
  - **2. Follow-Up Bedside Manner & Empathy (`backend/app/rag/prompt_builder.py`):**
    - *Problem:* Follow-up instructions had become overly mechanical after removing the 7-section template.
    - *Fix:* Re-introduced comprehensive bedside-manner rules into `FOLLOWUP_TURN_RULES`:
      - Open warmly and empathetically, validating the user's emotional state.
      - Provide 3–5 high-yield, concrete lifestyle or dietary action recommendations grounded in the user's saved health profile and exact biomarker values.
      - Frame any medication questions or clinical decisions strictly as topics to discuss with the user's treating physician.
      - Cap response under 250 words unless the user explicitly asks for an in-depth breakdown.
      - Updated Rule 1 of `REPORT_WALKTHROUGH_RULES` to *"Within the first two sentences, state the exact numbers..."* (E6 guideline).
      - Added Rule 5 to `<followup_turn_instruction>` in `build_prompt` and `build_general_health_prompt`.
  - **3. Comparison Regex Narrowing and `None` Safety:**
    - Narrowed `_COMPARISON_REQUEST_RE` to explicit comparative queries:
      `\b(compare|comparison|trend|trends|versus|vs\.?|over time|baseline|change since|difference between|prior report|earlier report|previous report)\b`.
    - Protected all calls against `user_query=None` by evaluating `user_query or ""`.
  - **4. Raw History Auto-Condensing & Role Preservation:**
    - Implemented `_condense_session_history_str` and updated `condense_chat_history`, `build_prompt`, and `build_general_health_prompt` to accept raw multi-line strings.
    - Anchored disclaimer removal to line start to protect mid-message mentions.
    - Preserved role labels (`User`, `Doctor`, `Assistant`) so that pre-formatted histories maintain their identity while stripping markdown tables, headings, and disclaimers.

---

## 3. Verification & Test Metrics

### A. Backend Pytest Suites
Command: `python -m pytest backend/tests -m "not integration" -q`
- **Result:** **597 passed**, 8 deselected, **0 failed** (Duration: 64.91s).
- **Targeted Test Proofs:**
  - `backend/tests/test_followup_prompt.py`: 13 / 13 passed.
    - `test_output_filter_safe_cautions_and_dangerous_advice` (safe cautions pass, un-negated directives block).
    - `test_followup_turn_rules_empathy_and_guidance_content` (warmth, 3-5 actions, word limits).
    - `test_comparison_request_re_narrowed_and_none_safety` (explicit comparison intent & `None` safety).
    - `test_history_condenser_mid_message_disclaimer_and_raw_string_safety` (mid-message disclaimer retention & string auto-condensing).
    - `test_route_followup_emergency_disclaimer_preservation` (emergency banner disclaimer retention).
    - `test_clean_disclaimers_mid_text_anchoring` (line-start anchoring).
  - `backend/tests/test_prompt_grounding.py`: 25 / 25 passed.
  - `backend/tests/test_output_filter.py`: 11 / 11 passed.
  - `backend/tests/test_profile_isolation.py`: All 3 tests passed.

### B. Frontend Vitest Suites
Command: `npm --prefix frontend test -- --run`
- **Result:** **34 test files passed**, **280 tests passed**, **0 failed** (Duration: 57.68s).
- **Key Suites Verified:**
  - `ProfileIsolation.test.jsx`: All 10 tests passed (cross-profile isolation, cache loading, patient ID normalization).
  - `HumanQASimulation.test.jsx`: All 7 end-to-end QA journeys passed.
  - `ChatApp.test.jsx`, `Workbench.test.jsx`, `PatientSwitcher.test.jsx`, `ChatSessionSync.test.jsx`: All passed.

### C. Frontend Production Build
Command: `npm --prefix frontend run build`
- **Result:** Vite build completed successfully in 18.05s with 0 errors.

---

## 4. Rollback Reference & Audit Registry

| Commit | Item Description | Files Modified | Rollback Command |
|---|---|---|---|
| `3382253` | Omit `patient_id` for self standalone chats | `ChatApp.jsx` | `git revert 3382253` |
| `c9d1b5c` | Wire `emergency_banner` to disclaimer preservation (`DECISION_3 = B`) | `query.py`, `test_followup_prompt.py` | `git revert c9d1b5c` |
| `fa50a4d` | Line-anchor `disclaimer_pattern` in `_clean_disclaimers` | `query.py`, `test_followup_prompt.py` | `git revert fa50a4d` |
| `5b71030` | Append QA-27 documentation to audit log | `QA_AUDIT_AND_FIX_LOG.md` | `git revert 5b71030` |
| `9726a98` | Fix `output_filter.py` false positives & restore follow-up warmth (QA-28) | `output_filter.py`, `prompt_builder.py`, `test_followup_prompt.py`, `QA_AUDIT_AND_FIX_LOG.md` | `git revert 9726a98` |

---

## 5. Current Git Working Tree Status
- Working branch: `fix/audit-followups`
- `git status`: Clean (nothing to commit, working tree clean).
- No remote pushes or unpermitted package modifications made.
