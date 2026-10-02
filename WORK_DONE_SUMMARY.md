# MediSkye — Work Done Summary

> Complete record of the codebase audit, fixes, and follow-up work.
> Last updated: after the D2 cascade-deletes migration.
> Repository: `D:\Mediskye Main\MediSkye\MediSkye`

---

## 1. Status at a Glance

| Item | Status |
|---|---|
| Phase 1 — Forensic bug audit (no edits) | ✅ Done, reported |
| Phase 2 — Fixes (5 groups) | ✅ Done |
| Phase 3 — Final audit report | ✅ `PHASE3_AUDIT_REPORT.md` |
| Follow-up — Theme-preserving logout | ✅ Done |
| Follow-up — Sidebar inline chat rename | ✅ Done |
| Follow-up — CI offline `test_query_stream` | ✅ Done |
| Follow-up — D2 cascade deletes + migration | ✅ Done |
| Backend tests | **72 passed**, 5 warnings |
| Frontend tests | **46 passed (9 files)** |
| Alembic | `current == heads == 3ee652733cc5` (single head) |
| Phase 0 security code | 🔒 Untouched |

### Test-count trajectory

| Stage | Backend | Frontend |
|---|---|---|
| Baseline | 58 | 28 |
| After Group 1 (logout) | 60 | 31 |
| After Group 2 (settings) | 62 | 34 |
| After Group 3 (bugs) | 66 | 39 |
| After Group 4 (CORS) | 71 | 39 |
| After Group 5 (cleanup) | 71 | 39 |
| After theme-preserve fix | 71 | 40 |
| After sidebar rename fix | 71 | 46 |
| After D2 cascade deletes | **72** | 46 |

### How to verify

```bash
# Backend
cd "D:/Mediskye Main/MediSkye/MediSkye/backend"
./.venv/Scripts/pytest.exe tests -q --no-header

# Frontend
cd "D:/Mediskye Main/MediSkye/MediSkye/frontend"
npm test
npm run build
```

---

## 2. The Engagement

A 3-phase full-codebase bug audit and cleanup for **MediSkye** (solo-dev medical RAG app).

- **Stack:** FastAPI + SQLAlchemy async + Alembic + SQLite/PostgreSQL backend; React 18 + Vite + Tailwind + react-router-dom frontend; Google Gemini.
- **Phase 1:** Read-only forensic audit (logout, settings, backend, frontend, DB/migrations, tests). **No edits.**
- **Phase 2:** Fixes after approval, run in 5 numbered groups with tests after each group.
- **Phase 3:** Consolidated Markdown report (`PHASE3_AUDIT_REPORT.md`).
- **Follow-ups:** Three additional targeted fixes requested after Phase 3.

**Severity found in Phase 1:** 1 CRITICAL, 6 HIGH, ~18 MEDIUM, ~20 LOW.

---

## 3. Phase 1 — Audit Findings & Resolution

### 3.1 Logout flow
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| L1 | CRITICAL | No logout UI existed anywhere | ✅ Added logout button + confirm modal |
| L2 | HIGH | `logout()` cleared only 5 localStorage keys | ✅ `clearLocalAuthStorage()` clears all auth keys |
| L3 | HIGH | Logout did not reset global app state | ✅ `handleLogout` resets state + redirects `/login` |
| L4 | MEDIUM | `ProtectedRoute` checks token presence only | ⏸ Deferred |
| L5 | MEDIUM | `user_revoked_at:{email}` dead code | ⏸ Left as-is (security-adjacent) |
| L6 | MEDIUM | `MockRedis` is in-process only | 📄 Documented |
| L7 | LOW | Logout errors swallowed silently | ✅ Handled |

### 3.2 Settings modal
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| S1 | HIGH | "Sign out of all devices" was fake | ✅ Removed |
| S2 | MEDIUM | Language selector not persisted | ✅ Persists `language_preference` |
| S3 | MEDIUM | Theme "System" not persisted | ✅ Persists raw pref incl. `system` |
| S4 | MEDIUM | "Change email" was a placeholder | ✅ Disabled + tooltip ("Coming soon — contact support") |
| S5 | LOW | "Privacy policy" placeholder | ✅ Disabled + "Coming soon" badge + tooltip |
| S6 | OK | "Export my data" disabled | Kept |
| S7 | MEDIUM | Memory-consent endpoint wiring | ✅ Kept `POST /users/me/memory/consent`; removed unused `getMemoryStatus` |
| S8 | OK | Profile fields persist | Verified |
| S9 | OK | Change password | Verified |
| S10 | LOW | Unused `language` prop to Sidebar | ✅ Cleaned |

### 3.3 Backend endpoints
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| E1 | HIGH | `create_dependent` dropped payload fields | ✅ Persists `height_cm`, `diet_type`, `activity_level`, `occupation` |
| E2 | HIGH | 7-day `ACCESS_TOKEN_EXPIRE_MINUTES` was never used | ✅ `create_access_token` now honors the config value |
| E3 | MEDIUM | `delete_user_me` cascade-only / AuditLog null | 📄 By design |
| E4 | MEDIUM | Deletion appears to skip original PDFs | ✅ Ruled NON-ISSUE (temp files deleted in `finally`) |
| E5 | LOW | `docs_url` ternary identical in both branches | ✅ Fixed |
| E6 | LOW | Login returned 400 instead of 401 | ✅ Fixed |
| E7 | MEDIUM | CORS wildcard `["*"]` with credentials | ✅ Explicit localhost allow-list |
| E8 | LOW | `SHOW_SPECIALIST_CONTACTS` defined twice | ✅ Removed duplicate |
| — | — | Dead endpoints | ✅ None found; dead FE exports removed |

### 3.4 Frontend
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| F2 | MEDIUM | Regenerate duplicated user message | ✅ Replaces trailing assistant message |
| F3 | MEDIUM | `setActivePdf` called inside state updater | ✅ Moved out of updater |
| F4 | MEDIUM | Stop-generation didn't abort request | ✅ `AbortController` wired through `api.js` |
| F5 | MEDIUM | Health profile weight created duplicate facts | ✅ Skip when unchanged |
| F6 | LOW | `handleClearAllChats` per-user key | 📄 Documented |
| F7 | LOW | Hardcoded `API_BASE` | ⏸ Deferred |
| F8 | LOW | Unused imports | ✅ Removed |
| F9 | LOW | `console.*` in production bundle | ✅ Routed through dev-only logger |
| F10 | LOW | `chat.createdAt` never set | ⏸ Deferred |
| F11 | LOW | `window.confirm` / `location` usage | ⏸ Deferred |
| F12 | LOW | `speech.js` used `alert()` | ✅ Replaced with logger warning |
| F13 | LOW | Fragile `document.querySelector('input[type="file"]')` | ⏸ Deferred |
| F14 | LOW | Unnecessary `import React` | 📄 Kept (idiomatic, zero risk) |
| F15 | MEDIUM | Consent-prompt sessionStorage not cleared on logout | ✅ Fixed |

### 3.5 Backend code quality
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| B1 | HIGH | 17× deprecated `datetime.utcnow()` | ✅ `datetime.now(UTC)` |
| B2 | MEDIUM | 13× `print()` | ✅ Replaced with `logging` |
| B3 | MEDIUM | `import fitz` (renamed package) | ✅ `import pymupdf as fitz` |
| B4 | LOW | Pydantic `class Config` | ✅ `model_config = ConfigDict(...)` |
| B6 | LOW | Broad `except` clauses | 📄 Documented |
| B7/B8 | LOW | Duplicate code | 📄 Documented |

### 3.6 Database / migrations
| ID | Sev | Finding | Resolution |
|---|---|---|---|
| D1 | OK | Single Alembic head | Verified |
| D2 | LOW | FKs lack `ON DELETE CASCADE` (orphaned rows) | ✅ Fixed (see §7) |
| D3 | LOW | Naive `DateTime` columns | ✅ Improved via tz-aware defaults |
| D4 | LOW | Dev `create_all` | 📄 Documented |
| D5 | INFO | Newest migration untracked | 📄 Noted |

### 3.7 Test coverage
| ID | Finding | Resolution |
|---|---|---|
| T1 | FE 28 tests / 6 files | Now 46 / 9 |
| T2 | BE 58 tests | Now 72 |
| T3 | No logout test | ✅ Added |
| T4 | No language/theme/dependent-create tests | ✅ Added |
| T5 | Zero-coverage FE components | 📄 Documented |
| T6 | Smoke test minimal | 📄 Documented |
| T7 | Stale `.lastfailed` | 📄 Noted |
| T8 | Existing memory/auth tests | Verified |

---

## 4. Phase 2 — Fixes by Group

### Group 1 — Logout flow
- `api.js`: `clearLocalAuthStorage()` helper.
- `ChatApp.jsx`: `handleLogout` resets global state and `navigate('/login', { replace: true })`.
- `Sidebar.jsx`: `LogOut` icon, `pendingLogout` state, "Log out" footer button, logout `ConfirmModal`.
- Tests: `frontend/src/test/logout.test.jsx`, `backend/tests/test_logout.py`, logout UI case in `Sidebar.test.jsx`.

### Group 2 — Settings wiring
- `ChatApp.jsx`: theme refactor — `getStoredThemePreference()` / `resolveDarkMode()`, `themePreference` + derived `darkMode`; persists raw pref incl. `'system'`; OS-theme listener only while `'system'`.
- `SettingsModal.jsx`: removed `getMemoryStatus` + `LogOut`; added `themePreference`/`setThemePreference` props, `onProfileUpdatedRef`, theme-sync effect, `handleLanguageChange`; Change email → disabled + tooltip; Privacy policy → disabled + badge + tooltip; removed "Sign out of all devices".
- Tests: `backend/tests/test_memory_consent.py`; 4 extended cases in `SettingsModal.test.jsx`.

### Group 3 — Bug fixes
- **E1**: `user.py` `create_dependent` persists the four personalization fields (`occupation` via `EncryptedString`). Test: `test_dependent_create.py`.
- **E2**: `core/auth.py` `create_access_token` uses `datetime.now(UTC)` and the configured `ACCESS_TOKEN_EXPIRE_MINUTES` instead of a hardcoded 15 min. Test: `test_token_expiry.py`.
  - **Policy note:** the configured lifetime is now intentionally **15 minutes** (short-lived for PHI safety, `TODO: refresh tokens in Phase 3`). The bug — config value being ignored — is fixed; the value is honored either way.
- **F2**: `handleSendMessage(userQuery, options = {})` with `{ appendUserMessage }`; `handleRegenerate` drops the trailing assistant message and re-sends without appending a duplicate user message.
- **F3**: `handleDetachDocument` computes `remainingDocs`/`nextActivePdf` outside the updater.
- **F4**: `abortControllerRef` (`useRef`); abort signal passed as 6th arg to `sendQueryStream`; `AbortError` swallowed; ref cleared in `finally`.
- **F5**: `HealthProfile.jsx` `lastSavedWeight` guard prevents duplicate weight facts.
- Tests: `frontend/src/test/ChatApp.test.jsx` (3), 2 added to `HealthProfile.test.jsx`.

### Group 4 — CORS (E7)
- `config.py`: `ALLOWED_ORIGINS: Annotated[List[str], NoDecode] = ["http://localhost:3000", "http://localhost:5173"]` + `@field_validator(..., mode="before")` to parse comma-separated env values.
- Appended `ALLOWED_ORIGINS` to root `.env` and `backend/.env.example`.
- Test: `backend/tests/test_cors.py` (5 tests).

### Group 5 — Cleanup
- **B1:** `datetime.utcnow()` → `datetime.now(UTC)` across models, endpoints, services, and 3 test files (11 columns via a local `utcnow()` helper).
- **B2:** 13× `print()` → module `logging` in `metrics.py`, `user.py`, `hybrid_search.py`, `intent_router.py`, `loader.py` (4), `retriever.py` (4).
- **B3:** `import fitz` → `import pymupdf as fitz` (4 sites).
- **B4:** Pydantic `class Config` → `model_config = ConfigDict(from_attributes=True)` (3 sites).
- **E8:** removed duplicate `SHOW_SPECIALIST_CONTACTS`.
- **E5:** `docs_url` now `None` when `DEBUG` is false.
- **E6:** login failure raises `401 Unauthorized`.
- **E4:** confirmed non-issue (temp PDFs deleted in `finally`).
- **F8:** removed unused imports (`Calendar`, `Users`, `HeartPulse`, `Briefcase/Ruler/Salad/Flame`).
- **F9/F12:** created dev-only `frontend/src/services/logger.js`; routed all `console.*` and `alert()` through it.
- Removed dead FE exports: `checkBackendHealth`, `getChatDocuments`, `attachChatDocument`, `updateUser`.
- **Verification:** backend 71 passed (warnings 164 → 5); frontend 39 passed; `npm run build` OK.

---

## 5. Follow-up Fixes

### 5.1 Theme-preserving logout
- Logout must not wipe UI preferences (`mediskye_theme`, `mediskye_language`) — they are UI prefs, **not** auth/PHI — to avoid a theme flash on re-login.
- `api.js` `clearLocalAuthStorage()` now uses module-scope `PRESERVED_STORAGE_KEYS = new Set(['mediskye_theme', 'mediskye_language'])`; removes `token` always and `mediskye_*` keys not in the preserve-set.
- `handleLogout` never resets theme state.
- Tests updated in `logout.test.jsx` (moved theme out of purge assertions; added dedicated preserve test).

### 5.2 Sidebar inline chat rename
- Root cause: rename input used `bg-transparent` with no border/padding, and buttons lacked `shrink-0`, so it rendered below with a layout jump.
- `Sidebar.jsx` rename branch now replaces the title in place: outer item `relative group flex items-center w-full min-w-0`; a `flex-1 flex items-center gap-1 min-w-0` row contains a styled `<input>` (`bg-gray-800 text-white px-2 py-1 rounded border border-gray-600 focus:outline-none focus:border-blue-500`) plus ✓/✗ buttons with `shrink-0`. Auto-focus via existing `renamingId` effect + `renameInputRef`.
- Tests: `frontend/src/test/SidebarRename.test.jsx` (6 tests).

### 5.3 CI offline `test_query_stream` fix
- **Problem:** `test_query_stream_after_pdf_upload_success` hit the real Gemini embedding API; CI's dummy `GOOGLE_API_KEY` caused `400 API key not valid`.
- **Fix (test-only, no app code changed):**
  - `FakeEmbedder` returns deterministic `[0.1] * 768` vectors for `embed_documents()` and `embed_query()`.
  - Patched `app.rag.retriever.get_embedder`, `app.services.chat_indexer.get_embedder`, and `app.rag.embedder.get_embedder` (covers upload FAISS build, retrieval/MMR, and local-import call sites).
  - Patched `google.genai.Client` for all LLM traffic (intent router, streaming answer, fact extraction).
  - Stubbed the fire-and-forget `process_chat_memory_extraction` background task with `AsyncMock` so it can never outlive the patch scope and reach the network.
  - `import fitz` → `import pymupdf as fitz`.
- **Verified:** `GOOGLE_API_KEY=invalid pytest tests/test_query_stream.py -v` passes; full suite passes offline.

---

## 6. Phase 3 Report

`PHASE3_AUDIT_REPORT.md` — findings table (severity/status), fixes by group, removed/wired/unwired features, logout before/after, test counts, files changed, manual verification checklist, deferred items.

---

## 7. D2 — Cascade Deletes (GDPR/HIPAA)

Deleting a user previously left orphaned child rows. Fixed.

### Model changes (`backend/app/db/models.py`)
| FK | Before | After |
|---|---|---|
| `dependent_profiles.user_id` | CASCADE | CASCADE *(already present)* |
| `documents.user_id` | *(none)* | **CASCADE** |
| `chats.user_id` | *(none)* | **CASCADE** |
| `chat_chunks.user_id` | CASCADE | CASCADE *(already present)* |
| `chat_chunks.chat_id` | CASCADE | CASCADE *(already present)* |
| `chat_documents.chat_id` | CASCADE | CASCADE *(already present)* |
| `chat_documents.document_id` | CASCADE | CASCADE *(already present)* |
| `patient_facts.user_id` | CASCADE | CASCADE *(already present)* |
| `audit_logs.user_id` | *(none)* | **SET NULL** (exception — audit trail preserved) |
| `chats.document_id` | *(none)* | **SET NULL** *(extra, required)* |

> ⚠️ `chats.document_id` was added beyond the original list: once FK enforcement is enabled, deleting a document (cascaded from the user delete) would otherwise violate the nullable `chats.document_id` reference. Without it, `DELETE FROM users` fails.

### SQLite FK enforcement (`backend/app/db/database.py`)
`@event.listens_for(engine.sync_engine, "connect")` sets `PRAGMA foreign_keys=ON`, guarded to SQLite URLs only.

### Migration
- Name: **`3ee652733cc5_add_cascade_deletes`** (down_revision `4c6654c33c56`).
- `alembic revision --autogenerate` was **unusable** on SQLite (spurious `NUMERIC()`→`UUID()` type diffs + `drop_constraint(None, ...)`). Replaced with a hand-written dialect-aware migration:
  - **SQLite:** `batch_alter_table(..., naming_convention=..., recreate="always")` — names the previously-unnamed reflected FKs, rebuilds the table, copies data.
  - **PostgreSQL/other:** drops the reflected constraint name and re-adds `create_foreign_key(..., ondelete=...)`.
- **Verified reversible:** in-place upgrade → downgrade → upgrade on the dev DB, row counts unchanged.

### Test
`backend/tests/test_cascade_deletes.py` — seeds user + dependent + document + chat + chunk + fact + audit_log; asserts `PRAGMA foreign_keys == 1`; raw SQL `DELETE FROM users WHERE id = :uid` (typed UUID bindparam — not an ORM delete); asserts all children gone and audit log present with `user_id IS NULL`.

---

## 8. Files Created

**Backend**
- `backend/tests/test_logout.py`
- `backend/tests/test_memory_consent.py`
- `backend/tests/test_dependent_create.py`
- `backend/tests/test_token_expiry.py`
- `backend/tests/test_cors.py`
- `backend/tests/test_cascade_deletes.py`
- `backend/alembic/versions/3ee652733cc5_add_cascade_deletes.py`

**Frontend**
- `frontend/src/services/logger.js`
- `frontend/src/test/logout.test.jsx`
- `frontend/src/test/ChatApp.test.jsx`
- `frontend/src/test/SidebarRename.test.jsx`

**Docs**
- `PHASE3_AUDIT_REPORT.md`
- `WORK_DONE_SUMMARY.md` (this file)

---

## 9. Files Modified (Phase 2 + follow-ups)

**Backend**
`app/api/v1/endpoints/user.py`, `auth.py`, `metrics.py`; `app/core/auth.py`, `config.py`; `app/db/database.py`, `models.py`; `app/main.py`; `app/rag/hybrid_search.py`, `intent_router.py`, `loader.py`, `retriever.py`; `app/schemas/dependent.py`, `user.py`; `app/services/chat_indexer.py`, `fact_persistence.py`, `pdf_service.py`; `tests/test_facts_api.py`, `test_multi_document.py`, `test_upload.py`, `test_query_stream.py`, `test_token_expiry.py`; root `.env`; `backend/.env.example`.

**Frontend**
`src/services/api.js`, `speech.js`; `src/components/ChatApp.jsx`, `ChatWindow.jsx`, `HealthProfile.jsx`, `PatientContextSelector.jsx`, `Profile.jsx`, `SettingsModal.jsx`, `Sidebar.jsx`; `src/test/ChatMessage.test.jsx`, `HealthProfile.test.jsx`, `SettingsModal.test.jsx`, `Sidebar.test.jsx`, `logout.test.jsx`.

**Database**
`mediskye.db` (dev DB upgraded to head).

---

## 10. Deferred / Documented (Not Fixed)

| Item | Reason |
|---|---|
| L4 — `ProtectedRoute` token-presence only | Enrichment, not a blocker |
| L5 — `user_revoked_at:{email}` dead code | Security-adjacent, out of scope |
| F7 — Hardcoded `API_BASE` | Deferred |
| F10 — `chat.createdAt` never set | Deferred |
| F11 — `window.confirm`/`location` usage | Deferred |
| F13 — Fragile file-input query | Deferred |
| F14 — `import React` kept | Idiomatic, zero risk |
| E3 — audit-log retention policy | Deliberate by design |
| D4 — dev `create_all` | Documented |
| T5 — zero-coverage FE components | Documented |

---

## 11. Constraints Honored Throughout

- 🔒 **Phase 0 security code untouched:** bcrypt 72-byte truncation, `secrets.compare_digest`, JWT secret isolation, startup kill-switches, Fernet.
- 🚫 **No commits, no pushes.**
- ➕ **No new dependencies.**
- ✅ **Every fix verified** with `pytest` / `npm test` / `npm run build`.
- 🔁 **Fixes applied in numbered groups**, tests run after each; nothing reverted.

---

## 12. Current Repository State

The Phase 2 audit work is committed (`2bf8e1d fix: full codebase audit — logout, settings wiring, cleanup`).

Uncommitted working-tree changes since then:

```
 M backend/app/core/auth.py            # token lifetime policy 15 min + refresh TODO
 M backend/app/db/database.py          # SQLite FK pragma (D2)
 M backend/app/db/models.py            # ondelete clauses (D2)
 M backend/tests/test_query_stream.py  # offline CI fix
 M backend/tests/test_token_expiry.py  # aligned with 15-min policy
?? backend/alembic/versions/3ee652733cc5_add_cascade_deletes.py
?? backend/tests/test_cascade_deletes.py
```

Alembic: `current == heads == 3ee652733cc5`.
