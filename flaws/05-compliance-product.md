# Compliance & Product

## 25. PHI handling without a documented policy

**Location:** System-wide

**Problem:** Users upload medical reports (protected health information in many jurisdictions). There is no documented:
- Encryption at rest
- Data retention period
- User consent flow
- Data deletion mechanism
- Access audit trail

**Impact:** Legal and ethical risk if real patient reports are used, even for a demo or MVP.

**Suggested fix:** Privacy policy, consent checkbox in UI, auto-delete uploads after N hours, encrypt stored vectors/files, log access minimally.

---

## 26. Disclaimer not enforced in API responses

**Location:** `README.md` (disclaimer section) vs `backend/rag/prompt_builder.py`

**Problem:** README warns the tool is not medical advice, but the prompt does not require a disclaimer in every model response.

**Impact:** Users may not see the disclaimer consistently in chat.

**Suggested fix:** Append a fixed disclaimer in the API layer or require it in the prompt template.

### First enhancement — FIXED

**What was done:** `append_disclaimer()` in `safety.py` runs on every LLM response; emergency responses include disclaimer too.

---

## 27. No emergency / triage escalation

**Location:** Product design (Phase 2 planned but not implemented)

**Problem:** Phase 2 triage is planned but Phase 1 can still answer urgent symptom questions without routing to emergency care.

**Impact:** Dangerous advice gap for acute symptoms mentioned in chat (not just in PDF).

**Suggested fix:** Keyword or classifier gate for emergency language; static response directing to emergency services.

### First enhancement — PARTIALLY FIXED

**What was done:** Keyword-based emergency gate in `safety.py` for common urgent phrases.

**Still open:** Regex-only detection misses many cases; full Phase 2 triage not built. See [future-plans](../future-plans/README.md).

---

## 28. No user data deletion endpoint

**Location:** `backend/main.py`

**Problem:** No API to delete uploaded report data or session vector store on user request.

**Impact:** Conflicts with privacy expectations and regulations (e.g. right to erasure).

**Suggested fix:** `DELETE /session/{id}` or similar to remove stored chunks and files.

---

## 29. README setup inconsistencies

**Location:** `README.md`

**Problems:**
- Clone URL mixes placeholder and real repo link in one line.
- Project structure lists `.env` at root but setup only mentions `GOOGLE_API_KEY` (no frontend API URL).
- "Chat history preserved" overstates current behavior (session-only).

**Suggested fix:** Single canonical clone URL, accurate feature list, env vars for both backend and frontend.

### Second enhancement — PARTIALLY FIXED

**What was done:** Production README rewrite with env vars, architecture diagrams, and accurate model name.

**Still open:** README Phase 1 still says "Chat history preserved" — history is session-only until refresh (#17).

---

## 40. No upload consent for PHI

**Location:** `frontend/streamlit_app.py`

**Problem:** Users can upload real medical reports with no privacy notice or explicit consent checkbox.

**Impact:** Legal/ethical gap before handling PHI at scale.

**Suggested fix:** Consent modal before first upload; link to privacy policy. See [future-plans](../future-plans/README.md).

**Status:** OPEN

---

## 41. Emergency detection is keyword-only

**Location:** `backend/rag/safety.py`

**Problem:** `is_emergency_query()` uses regex patterns only. Misses nuanced emergencies; may false-positive on historical report text.

**Impact:** Incomplete safety coverage for a medical product.

**Suggested fix:** ML classifier, Gemini safety tier, or structured triage flow. See [future-plans](../future-plans/README.md).

**Status:** OPEN

