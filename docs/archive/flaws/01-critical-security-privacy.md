# Critical — Security & Privacy

## 1. Shared in-memory state (no per-user isolation) — FIXED

**Location:** `backend/main.py`, `frontend/streamlit_app.py`

**Problem:** A single global `vectorstore` variable holds the uploaded report for all users. Every new upload overwrites it. All queries use whichever report was uploaded last.

**Impact:**
- User A's medical report can answer User B's questions (privacy breach).
- State is lost on server restart or when Render spins down (reliability).
- Cannot support multiple concurrent users.

**Solution implemented:**
- Replaced the single global `vectorstore` with `vectorstores: dict[str, object]`, keyed by validated UUID session IDs.
- The Streamlit frontend generates a unique `session_id` per browser session (`st.session_state.session_id`) and sends it on every upload via the `X-Session-ID` header and on every query in the JSON body.
- Upload and query handlers validate the session ID format before use, so each user only reads/writes their own vector store.

**Remaining limitation:** Vector stores are still in-memory and will be lost on server restart or Render cold start. Persistent storage (Redis, disk-backed FAISS) is a future improvement.

---

## 2. Sensitive data exposed via GET — FIXED

**Location:** `backend/main.py` — `/query` endpoint; `frontend/streamlit_app.py`

**Problem:** Queries are sent as GET request query parameters (`?query=...`).

**Impact:**
- Questions appear in server access logs, browser history, analytics, and referrer headers.
- Medical questions are sensitive PHI-adjacent data.

**Solution implemented:**
- Removed `GET /query`. Added `POST /query` with a `QueryRequest` body (`session_id`, `query`).
- Updated the Streamlit client to call `requests.post(..., json={...})` so health questions are sent in the request body, not the URL.

---

## 3. No authentication, rate limits, or upload guards

**Location:** `backend/main.py`

**Problem:**
- Public API with no auth.
- No file size limit on uploads.
- No validation beyond file extension (not content-type or PDF structure).
- No rate limiting.

**Impact:**
- Abuse and unexpected Gemini API costs.
- DoS via large file uploads.
- Malicious or non-PDF files may cause crashes.

**Suggested fix:** Add API keys or session auth, `max_upload_size`, PDF magic-byte validation, and rate limiting (e.g. slowapi).

### Second enhancement — FIXED

**What was done:**
- Added `backend/rag/guards.py` with:
  - Optional API key auth via `X-API-Key` header (enforced when `MEDISKYE_API_KEY` env var is set).
  - PDF magic-byte validation (`%PDF`) before processing.
  - Configurable upload size limit via `MEDISKYE_MAX_UPLOAD_MB` (default 10 MB).
- Integrated `slowapi` rate limiting in `backend/main.py`:
  - `POST /upload` — 5 requests/minute per IP.
  - `POST /query` — 20 requests/minute per IP.
- Updated `frontend/streamlit_app.py` to send `X-API-Key` when configured.

**Verification:** Upload rejects non-PDF bytes and oversized files; rate limits return 429 when exceeded; API key returns 401 when env is set and header is missing/wrong.

**Remaining limitation:** Auth is optional until `MEDISKYE_API_KEY` is set in production. No per-user accounts yet — only shared API key + session ID.

---

## 4. Temporary files never deleted — FIXED

**Location:** `backend/main.py` — `/upload` handler

**Problem:** Uploads use `NamedTemporaryFile(delete=False)` and the temp path is never removed with `os.unlink()`.

**Impact:** Disk usage grows over time on the server.

**Solution implemented:**
- Wrapped PDF processing in `try/finally`.
- After extraction (success or failure), the temp file is removed with `os.unlink()` if it still exists.
- Temp files use a `.pdf` suffix for clearer debugging on disk before cleanup.

---

## 5. Weak medical safety layer — FIXED

**Location:** `backend/rag/prompt_builder.py`, `backend/rag/safety.py`, `backend/main.py`

**Problem:** The prompt instructs the model to name possible diseases from out-of-range values, but there are no guardrails for:
- Emergency symptoms (e.g. chest pain → seek emergency care).
- Hallucinated diagnoses.
- Mandatory "not medical advice" disclaimer in every response.

**Impact:** Users may treat AI output as diagnosis; liability and harm risk in a healthcare context.

**Solution implemented:**
- Added `backend/rag/safety.py` with emergency keyword detection, a standard medical disclaimer, and helpers to append the disclaimer to every response.
- `/query` now short-circuits emergency-like queries (chest pain, trouble breathing, stroke signs, etc.) and returns an immediate emergency-services message without calling the LLM.
- Rewrote `prompt_builder.py` to forbid definitive diagnoses, require cautious language, ground answers in report excerpts only, and instruct the model to include the disclaimer.
- `append_disclaimer()` runs on every LLM response so the disclaimer appears even if the model omits it.

---

## 30. Missing `backend/rag/safety.py` (broken imports)

**Location:** `backend/main.py`, `backend/rag/prompt_builder.py`

**Problem:** Passes 1–2 imported `rag.safety` but the file was never committed. Backend failed on startup with `ModuleNotFoundError`.

**Impact:** Entire backend non-functional despite other enhancements being present.

**Suggested fix:** Restore `safety.py` with all symbols used by `main.py` and `prompt_builder.py`.

### Third enhancement — FIXED

**What was done:**
- Restored `backend/rag/safety.py` with `MEDICAL_DISCLAIMER`, `is_emergency_query()`, `get_emergency_response()`, and `append_disclaimer()`.
- Verified imports chain: `main.py` → `safety.py`, `prompt_builder.py` → `MEDICAL_DISCLAIMER`.

**Verification:** Backend starts without `ModuleNotFoundError` for `rag.safety`.

---

## 36. Session vector stores never cleaned up (memory leak)

**Location:** `backend/main.py` — `vectorstores` dict

**Problem:** Every browser session adds an entry to `vectorstores`. Nothing removes old sessions.

**Impact:** Server memory grows indefinitely on a long-running instance.

**Suggested fix:** TTL-based cleanup, `DELETE /session/{id}`, or move stores to Redis with expiry. See [future-plans](../future-plans/README.md).

**Status:** OPEN

---

## 37. Auth disabled when `MEDISKYE_API_KEY` unset

**Location:** `backend/rag/guards.py`

**Problem:** If `MEDISKYE_API_KEY` is not set, `verify_api_key()` is a no-op and the API is fully public.

**Impact:** Easy to deploy insecurely; anyone can abuse Gemini quota.

**Suggested fix:** Require API key in production via env validation at startup, or OAuth/JWT. See [future-plans](../future-plans/README.md).

**Status:** OPEN (partial fix from pass 2 — optional key only)
