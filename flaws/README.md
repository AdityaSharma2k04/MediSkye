# MediSkye — Known Flaws & Issues

This folder documents identified flaws in the MediSkye codebase. It is **local-only** (listed in `.gitignore`) and is not pushed to GitHub.

Use it as a step-by-step record of what was wrong and what was fixed in each enhancement pass.

For **what to build next** (OAuth, PostgreSQL, Redis, etc.), see the local [`future-plans/`](../future-plans/README.md) folder.

## Index

| # | Category | File |
|---|----------|------|
| 1 | Critical — Security & Privacy | [01-critical-security-privacy.md](./01-critical-security-privacy.md) |
| 2 | RAG & Accuracy | [02-rag-accuracy.md](./02-rag-accuracy.md) |
| 3 | Frontend | [03-frontend.md](./03-frontend.md) |
| 4 | Backend & Operations | [04-backend-ops.md](./04-backend-ops.md) |
| 5 | Compliance & Product | [05-compliance-product.md](./05-compliance-product.md) |

---

## Enhancement history

### First enhancement (critical security & safety)

| # | Issue | Status |
|---|--------|--------|
| 1 | Shared in-memory state | Fixed — per-session vector stores |
| 2 | GET `/query` exposes questions in URL | Fixed — `POST /query` with JSON body |
| 4 | Temp files never deleted | Fixed — `try/finally` + `os.unlink()` |
| 5 | Weak medical safety layer | Fixed — emergency gate, safer prompt, mandatory disclaimer |

### Second enhancement (auth, RAG quality, docs)

| # | Issue | Status |
|---|--------|--------|
| 3 | No auth, rate limits, or upload guards | Fixed — guards.py, slowapi, PDF/size validation |
| 6 | PyPDF2 struggles with real reports | Fixed — PyPDF2 + PyMuPDF + OCR + empty-text error |
| 7 | Small chunks split context | Fixed — 1200/200 chunks, page metadata preserved |
| 8 | Only top-3 chunks retrieved | Fixed — MMR search, k=8, fetch_k=24 |
| 10 | README vs code model mismatch | Fixed — README aligned to Gemini 1.5 Flash |
| 11 | Embedder description mismatch | Fixed — README says Google-only |

### Third enhancement (compatibility & integration)

**Goal:** Make all modules from passes 1–2 work together without import errors or broken references.

| # | Issue | Status |
|---|--------|--------|
| 30 | Missing `backend/rag/safety.py` (broken imports) | Fixed — file restored |
| 13 | Wrong `frontend/requirements.txt` | Fixed — `streamlit`, `requests` only |
| 22 | `.env` path ambiguity | Fixed — explicit root path in main.py + embedder.py |
| 31 | `start.sh` hardcoded port | Fixed — uses `${PORT:-10000}` for Render |
| 32 | `st.secrets` crash without secrets file | Fixed — safe `get_api_key()` wrapper |

**Step 3 flaws documented in:** [01-critical-security-privacy.md](./01-critical-security-privacy.md) (#30), [03-frontend.md](./03-frontend.md) (#13, #32), [04-backend-ops.md](./04-backend-ops.md) (#18, #22, #31).

---

## Priority summary (remaining open items)

| Priority | Count | Focus |
|----------|-------|--------|
| High | 6 | Streamlit rerun bugs, cold start data loss, Gemini error handling, memory leak |
| Medium | 7 | CORS, health check, hybrid search, session delete, partial metadata |
| Low | 4 | Chat persistence, startup validation, README chat claim, auth optional by default |

## Suggested fix order (remaining)

1. Streamlit form + dedupe for upload/query reruns (#12, #33, #34)
2. Error handling for Gemini + non-JSON responses (#19, #35)
3. Persistent vector storage / Redis (#24, #36) — see [future-plans](../future-plans/README.md)
4. Health endpoint + startup key check (#21, #23)
5. OAuth + JWT + PostgreSQL (#37+) — see [future-plans](../future-plans/README.md)
