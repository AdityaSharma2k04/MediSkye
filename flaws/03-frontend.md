# Frontend

## 12. Duplicate API calls on every Streamlit rerun

**Location:** `frontend/streamlit_app.py`

**Problem:** The app uses `st.text_input` and immediately runs `if user_input:` to call the API. Streamlit reruns the entire script on interaction. Any rerun while the input field has text triggers another `/query` call.

**Impact:**
- Same question sent multiple times.
- Duplicate chat history entries.
- Unnecessary API cost and latency.

**Suggested fix:** Use a form with `st.form_submit_button`, or track last-queried text in `st.session_state` and skip if unchanged.

---

## 13. Missing dependencies in `frontend/requirements.txt`

**Location:** `frontend/requirements.txt`

**Problem:**
- Uses `streamlit` and `requests` but neither is listed.
- Lists backend-only packages (`fastapi`, `uvicorn`, `PyPDF2`, `langchain`, etc.) that the Streamlit app does not import.

**Impact:** Fresh installs of the frontend fail or pull unnecessary dependencies.

**Suggested fix:** Minimal frontend deps, e.g. `streamlit`, `requests` (and pin versions).

### Third enhancement — FIXED

**What was done:**
- Replaced `frontend/requirements.txt` with only `streamlit` and `requests`.

**Verification:** `pip install -r requirements.txt` in `frontend/` installs what the app actually imports.

---

## 14. Hardcoded production backend URL

**Location:** `frontend/streamlit_app.py`

```python
API_BASE = "https://mediskye-51pi.onrender.com"
```

**Problem:** No environment-based configuration for local development vs production.

**Impact:** Local frontend always hits deployed backend; harder to test end-to-end locally.

**Suggested fix:** `API_BASE = os.getenv("MEDISKYE_API_URL", "http://localhost:8000")` and document in README.

### Second enhancement — FIXED

**What was done:** `API_BASE = os.getenv("MEDISKYE_API_URL", "https://mediskye-51pi.onrender.com")` — configurable via env, defaults to production URL.

**Remaining limitation:** Default is still production if env unset; local dev must set `MEDISKYE_API_URL=http://localhost:8000`.

---

## 15. Generic error messages

**Location:** `frontend/streamlit_app.py`

**Problem:** On failure, UI shows a generic message and does not display backend error payloads (e.g. `{"error": "No PDF uploaded yet."}`).

**Impact:** Users cannot tell upload vs query vs server errors apart.

**Suggested fix:** Parse `res.json()` for `error` or `detail` and show it in `st.error()`.

### Second enhancement — PARTIALLY FIXED

**What was done:** Query and upload paths parse `detail` and `error` from JSON responses.

**Still open:** No try/except if response is not JSON (e.g. Render 502 HTML) — see #35.

---

## 16. Invalid chat message role

**Location:** `frontend/streamlit_app.py`

**Problem:** `st.chat_message(speaker if speaker == "You" else "assistant")` — `"You"` is not a standard Streamlit chat role (`"user"` / `"assistant"`).

**Impact:** Possible UI inconsistency or warnings depending on Streamlit version.

**Suggested fix:** Map `"You"` → `"user"` for `st.chat_message`.

### Second enhancement — FIXED

**What was done:** Uses `"user"` and `"assistant"` roles in `st.chat_message()`.

---

## 17. Chat history lost on refresh

**Location:** `frontend/streamlit_app.py`

**Problem:** History lives only in `st.session_state`. Browser refresh clears it.

**Impact:** Contradicts README claim that "Chat history preserved in the UI" — only preserved within a single session tab until refresh.

**Suggested fix:** Clarify in README, or persist history (localStorage via custom component, or backend session store).

---

## 32. `st.secrets` crash without secrets file

**Location:** `frontend/streamlit_app.py`

**Problem:** Direct `st.secrets.get(...)` can throw when `.streamlit/secrets.toml` does not exist locally.

**Impact:** Frontend crashes on local dev without Streamlit secrets configured.

**Suggested fix:** Wrap secrets access in try/except; prefer env var first.

### Third enhancement — FIXED

**What was done:**
- Added `get_api_key()` that checks `os.getenv` first, then `st.secrets` inside try/except.

---

## 33. PDF re-uploaded on every Streamlit rerun

**Location:** `frontend/streamlit_app.py` — `if uploaded_file:` block

**Problem:** After a file is selected, `uploaded_file` stays truthy on every rerun. Any UI interaction re-triggers `POST /upload`.

**Impact:** Duplicate uploads, wasted API calls, chat history reset unexpectedly.

**Suggested fix:** Use `st.form` + submit button, or track `last_uploaded_file_id` in session state.

**Status:** OPEN

---

## 34. Duplicate query on Streamlit rerun (same as #12)

**Location:** `frontend/streamlit_app.py`

**Problem:** Same as #12 — still present after passes 1–3. `if user_input:` fires on every rerun while text remains in the box.

**Suggested fix:** `st.form_submit_button` or dedupe with `last_query` in session state.

**Status:** OPEN

---

## 35. Crash on non-JSON error responses

**Location:** `frontend/streamlit_app.py` — upload and query handlers

**Problem:** `res.json()` called without try/except. Render 502/504 HTML responses cause frontend crash.

**Impact:** User sees Streamlit traceback instead of a friendly error during cold start or outage.

**Suggested fix:** Check `Content-Type`, wrap `res.json()` in try/except, show `res.text` fallback.

**Status:** OPEN



### Second enhancement — FIXED

**What was done:**
- Added `frontend/streamlit_app.py` with a `cleanup_temp_files()` function that removes all temporary files in the `temp_dir`.
- Added `frontend/streamlit_app.py` with a `cleanup_temp_files()` function that removes all temporary files in the `temp_dir`.

**Note:** The above Second enhancement entry was incorrectly documented. No `cleanup_temp_files()` exists in the frontend. See Third enhancement (#32) for actual pass 3 fixes.
