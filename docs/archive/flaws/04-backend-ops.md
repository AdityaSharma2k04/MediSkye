# Backend & Operations

## 18. Missing `python-dotenv` in backend requirements

**Location:** `backend/requirements.txt` vs `backend/main.py`, `backend/rag/embedder.py`

**Problem:** Code calls `load_dotenv()` but `python-dotenv` is not listed in `backend/requirements.txt`.

**Impact:** Deployments that install strictly from requirements may fail at import/runtime.

**Suggested fix:** Add `python-dotenv` to `backend/requirements.txt`.

### Second enhancement — FIXED

**What was done:** Added `python-dotenv` to `backend/requirements.txt`.

---

## 19. No error handling in API routes

**Location:** `backend/main.py`

**Problem:** No try/except around:
- PDF text extraction
- Vector store creation
- Gemini API calls

**Additional risk:** `response.text` can raise if Gemini blocks content for safety filters.

**Impact:** Unhandled exceptions return opaque 500 errors; poor UX and hard debugging.

**Suggested fix:** Wrap operations in try/except; return structured JSON errors; handle blocked/safety responses from Gemini.

**Status:** OPEN

---

## 20. CORS misconfiguration

**Location:** `backend/main.py`

```python
allow_origins=["*"],
allow_credentials=True,
```

**Problem:** Browsers treat `*` origin with credentials as invalid per CORS spec. This combination is a common misconfiguration.

**Impact:** Unexpected CORS behavior in some clients; security smell in production.

**Suggested fix:** List explicit frontend origins; set `allow_credentials=False` if using `*`.

**Status:** OPEN

---

## 21. No health check endpoint

**Location:** `backend/main.py`

**Problem:** No `/health` or `/` readiness route.

**Impact:** Harder to monitor Render uptime, cold starts, and load balancer health checks.

**Suggested fix:** Add `GET /health` returning `{"status": "ok"}`.

**Status:** OPEN

---

## 22. `.env` path ambiguity

**Location:** `backend/main.py`, `backend/rag/embedder.py`; README

**Problem:** README says `.env` lives at repo root, but `load_dotenv()` with no path looks in the current working directory (often `backend/` when running uvicorn).

**Impact:** `GOOGLE_API_KEY` may not load locally unless env is set elsewhere.

**Suggested fix:** `load_dotenv(Path(__file__).resolve().parent.parent / ".env")` or document running from root with explicit env export.

### Third enhancement — FIXED

**What was done:**
- `main.py`: `load_dotenv(Path(__file__).resolve().parent.parent / ".env")`
- `embedder.py`: `load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")`

Both resolve to the project root `.env` as documented in README.

---

## 23. No API key validation at startup

**Location:** `backend/main.py`

**Problem:** If `GOOGLE_API_KEY` is missing, failure happens only on first embed/query call.

**Impact:** Server appears healthy until first real use.

**Suggested fix:** Validate key presence (and optionally a test embed) on startup or in `/health`.

**Status:** OPEN

---

## 24. Render cold start + ephemeral memory

**Location:** Deployment architecture

**Problem:** Free/low-tier Render instances sleep and lose in-memory `vectorstore`. Users must re-upload after cold start.

**Impact:** Poor UX; appears "broken" after idle period.

**Suggested fix:** Persistent vector storage; keep-alive ping; paid tier with min instances — see [future-plans](../future-plans/README.md) for PostgreSQL + Redis.

**Status:** OPEN

---

## 31. `start.sh` hardcoded port

**Location:** `backend/start.sh`

**Problem:** Script used fixed port `10000`. Render injects `$PORT` dynamically.

**Impact:** Deploy may fail or listen on wrong port if Render expects `$PORT`.

**Suggested fix:** Use `${PORT:-10000}` in uvicorn command.

### Third enhancement — FIXED

**What was done:** `uvicorn main:app --host=0.0.0.0 --port="${PORT:-10000}"`

---

### Second enhancement — FIXED

**What was done:**
- Added `backend/main.py` with a `cleanup_temp_files()` function that removes all temporary files in the `temp_dir`.
- Added `backend/main.py` with a `cleanup_temp_files()` function that removes all temporary files in the `temp_dir`.

**Note:** The above Second enhancement entry was incorrectly documented. No `cleanup_temp_files()` exists in main.py. Temp file cleanup is handled inline in the `/upload` handler (flaw #4, pass 1).
