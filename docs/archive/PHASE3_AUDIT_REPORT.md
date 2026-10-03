# MediSkye — Full Codebase Bug Audit & Settings Cleanup

**Scope:** Backend (FastAPI + SQLAlchemy async + Alembic) and frontend (React 18 + Vite + Tailwind).
**Date context:** Post–Phase 2 verification.
**Rules honored:** No Phase 0 security code touched (Fernet, JWT-secret isolation, startup kill-switches, bcrypt 72-byte truncation, `secrets.compare_digest`). No commits/pushes. No new dependencies.

---

## 1. Executive Summary

| Metric | Before | After |
|---|---|---|
| Backend tests | 58 passed | **71 passed** |
| Backend warnings | 164 | **5** |
| Frontend tests | 28 passed (6 files) | **39 passed (8 files)** |
| Frontend production build | — | **✅ succeeds** |

Key outcomes:
- The **Critical** logout defect (no reachable logout UI) and all **High**-severity findings (L2, L3, S1, E1, E2, B1) are fixed.
- Settings are now genuinely wired (theme, language, change-password, memory consent) or explicitly disabled with tooltips.
- Deprecated APIs removed (`datetime.utcnow`, `import fitz`, Pydantic `class Config`), `print()` replaced with structured logging, dead frontend exports/imports removed, and console logging routed through a dev-only logger.

---

## 2. Audit Findings & Resolution Status

Severity legend: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low · ℹ️ Info/N-A

### 2.1 Logout flow
| ID | Sev | Finding | Location | Status |
|---|---|---|---|---|
| L1 | 🔴 | No logout UI was reachable anywhere in the app | `Sidebar.jsx` / `ChatApp.jsx` | ✅ Fixed |
| L2 | 🟠 | `logout()` cleared only 5 localStorage keys, leaving `mediskye_*` residue | `services/api.js` | ✅ Fixed |
| L3 | 🟠 | Logout did not reset global app state (conversations/active doc/patient) | `ChatApp.jsx` | ✅ Fixed |
| L4 | 🟡 | `ProtectedRoute` checks token presence only (no expiry/validity) | `App.jsx` | ⏸ Deferred (design) |
| L5 | 🟡 | `user_revoked_at:{email}` blocklist branch is dead code | `core/auth.py` | ⏸ Left in place (security-adjacent) |
| L6 | 🟡 | `MockRedis` blocklist is in-process only (lost on restart) | `core/redis_client.py` | ⏸ Documented |
| L7 | 🟢 | Logout errors were swallowed silently | `services/api.js` | ✅ Fixed (dev logger) |

### 2.2 Settings modal
| ID | Sev | Finding | Status |
|---|---|---|---|
| S1 | 🟠 | "Sign out of all devices" was fake (called single logout) | ✅ Removed |
| S2 | 🟡 | Language selection was not persisted | ✅ Wired (`language_preference`) |
| S3 | 🟡 | Theme "System" choice was not persisted | ✅ Wired (raw preference persisted) |
| S4 | 🟡 | "Change email" was a non-functional placeholder | ✅ Disabled + tooltip |
| S5 | 🟢 | "Privacy policy" was a non-functional placeholder | ✅ Disabled + "Coming soon" |
| S6 | ℹ️ | "Export my data" disabled | ✅ Left as-is (by design) |
| S7 | 🟡 | Memory consent used `POST /users/me/memory/consent`; `getMemoryStatus` unused | ✅ Endpoint kept per decision; unused import removed |
| S8 | ℹ️ | Profile fields persist | ✅ No change needed |
| S9 | ℹ️ | Change-password flow works | ✅ Verified + covered by test |
| S10 | 🟢 | `ChatApp` passes `language` to `Sidebar` which never destructured it | ✅ Cleaned |

### 2.3 Backend endpoints
| ID | Sev | Finding | Status |
|---|---|---|---|
| E1 | 🟠 | `create_dependent` silently dropped `height_cm`, `diet_type`, `activity_level`, `occupation` | ✅ Fixed + test |
| E2 | 🟠 | `ACCESS_TOKEN_EXPIRE_MINUTES` (7d) was never used; tokens defaulted to **15 min** | ✅ Fixed + test |
| E3 | 🟡 | `delete_user_me` cascade-only; `AuditLog.user_id` nulled; no blocklist clear | ⏸ By design (audit retention; JWT dies with user) |
| E4 | 🟡 | Account deletion suspected to skip original PDFs | ✅ Verified non-issue (temp files deleted in `finally`) |
| E5 | 🟢 | `docs_url="/docs" if DEBUG else "/docs"` — both branches identical | ✅ Fixed (`None` when not DEBUG) |
| E6 | 🟢 | Failed login returned `400` instead of `401` | ✅ Fixed (`status.HTTP_401_UNAUTHORIZED`) |
| E7 | 🟡 | CORS allowed `["*"]` | ✅ Fixed (explicit localhost allow-list) |
| E8 | 🟢 | `SHOW_SPECIALIST_CONTACTS` defined twice in `config.py` | ✅ Deduplicated |
| — | ℹ️ | No dead backend endpoints | ✅ Verified |

### 2.4 Frontend bugs
| ID | Sev | Finding | Status |
|---|---|---|---|
| F2 | 🟡 | Regenerate appended a duplicate assistant message | ✅ Fixed + test |
| F3 | 🟡 | `setActivePdf` called inside a `setConversations` updater (double-invoke hazard) | ✅ Fixed + test |
| F4 | 🟡 | Stop-generation did not abort the in-flight request | ✅ Fixed (AbortController) + test |
| F5 | 🟡 | Repeated saves created duplicate weight facts | ✅ Fixed + test |
| F6 | 🟢 | `handleClearAllChats` used a per-user key inconsistently | ⏸ Documented |
| F7 | 🟢 | `API_BASE` hardcoded | ⏸ Deferred (env plumbing out of scope) |
| F8 | 🟢 | Unused imports | ✅ Removed |
| F9 | 🟢 | Raw `console.*` calls | ✅ Routed through dev-only logger |
| F10 | 🟢 | `chat.createdAt` never set | ⏸ Deferred |
| F11 | 🟢 | `window.confirm` / `window.location.href` | ⏸ Deferred (UI refactor) |
| F12 | 🟢 | `speech.js` used blocking `alert()` | ✅ Replaced with graceful no-op |
| F13 | 🟢 | Fragile `document.querySelector('input[type="file"]')` | ⏸ Deferred |
| F14 | 🟢 | Unnecessary `import React` | ⏸ Intentionally kept (idiomatic, zero risk) |
| F15 | 🟡 | Consent-prompt `sessionStorage` flag not cleared on logout | ✅ Fixed (`clearLocalAuthStorage`) |

### 2.5 Backend code quality
| ID | Sev | Finding | Status |
|---|---|---|---|
| B1 | 🟠 | 17× deprecated `datetime.utcnow()` | ✅ Fixed (`datetime.now(UTC)` + local helper) |
| B2 | 🟡 | 13× `print()` | ✅ Replaced with `logging` |
| B3 | 🟡 | Deprecated `import fitz` (package renamed to `pymupdf`) | ✅ Fixed (4 sites) |
| B4 | 🟢 | Pydantic `class Config` | ✅ Migrated to `ConfigDict` (3 sites) |
| B6 | 🟢 | Broad `except` clauses | ⏸ Documented |
| B7/B8 | 🟢 | Minor duplication | ⏸ Documented |

### 2.6 Database / migrations
| ID | Sev | Finding | Status |
|---|---|---|---|
| D1 | ℹ️ | `alembic current` == `heads` == `4c6654c33c56` (single head) | ✅ Verified |
| D2 | 🟢 | FKs lack `ondelete CASCADE` | ⏸ Documented |
| D3 | 🟢 | Naive `DateTime` columns | ✅ Improved (tz-aware defaults) |
| D4 | 🟢 | `create_all` in dev | ⏸ Documented |
| D5 | ℹ️ | Newest migration untracked in git | ℹ️ Working-tree state |

### 2.7 Test coverage
| ID | Sev | Finding | Status |
|---|---|---|---|
| T1/T2 | ℹ️ | FE 28 / BE 58 baseline | ✅ Now FE 39 / BE 71 |
| T3 | 🟠 | No logout test | ✅ Added (FE + BE) |
| T4 | 🟡 | No language/theme/dependent-create tests | ✅ Added |
| T5 | 🟢 | Zero-coverage FE components | ⏸ Documented |
| T6 | 🟢 | Smoke test coverage minimal | ⏸ Documented |
| T7 | 🟢 | Stale `.lastfailed` | ℹ️ |
| T8 | ℹ️ | Existing memory/auth tests | ✅ Extended |

---

## 3. Fixes Applied (by group)

### Group 1 — Logout flow
- `services/api.js`: added `clearLocalAuthStorage()` — removes `token`, every `mediskye_*` key, and `mediskye_consent_prompted` (sessionStorage); preserves unrelated keys. `logout()` invokes it in a `finally` block.
- `ChatApp.jsx`: `handleLogout` resets global state, then `navigate('/login', { replace: true })`.
- `Sidebar.jsx`: added a footer **Log out** button with a `ConfirmModal` ("Log out of MediSkye?").
- New tests: `frontend/src/test/logout.test.jsx`, `backend/tests/test_logout.py`, plus a UI test in `Sidebar.test.jsx`.

### Group 2 — Settings wiring
- `ChatApp.jsx`: theme refactor — `getStoredThemePreference()` / `resolveDarkMode()`, raw preference (`light`/`dark`/`system`) persisted, OS-theme listener active only while `system`.
- `SettingsModal.jsx`: removed the fake "Sign out of all devices" and unused `getMemoryStatus`/`LogOut` imports; theme preference props + sync effect; language change persists via `updateProfile({ language_preference })` with optimistic update/revert + toast; "Change email" and "Privacy policy" disabled with tooltips; profile-fields save verified; change-password verified.
- New tests: `backend/tests/test_memory_consent.py`, 4 new cases in `SettingsModal.test.jsx`.

### Group 3 — Bug fixes
- **E1** `user.py::create_dependent` now persists `height_cm`, `diet_type`, `activity_level`, `occupation` (encrypted) → `test_dependent_create.py`.
- **E2** `core/auth.py::create_access_token` now uses `datetime.now(UTC)` and defaults to `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)` (7 days). JWT signature verification, blocklist check, and expiry semantics preserved → `test_token_expiry.py`.
- **F2** `handleSendMessage(query, { appendUserMessage })`; `handleRegenerate` drops only the trailing assistant message and re-streams without duplicating the user bubble.
- **F3** `handleDetachDocument` computes the next active PDF outside the state updater.
- **F4** `AbortController` wired through `sendQueryStream(..., signal)`; Stop aborts and resets; `AbortError` swallowed.
- **F5** `HealthProfile.jsx` skips re-saving an unchanged weight fact.
- New tests: `frontend/src/test/ChatApp.test.jsx` (F2/F3/F4), 2 cases in `HealthProfile.test.jsx`.

### Group 4 — CORS (E7)
- `config.py`: `ALLOWED_ORIGINS: Annotated[List[str], NoDecode]` with a `field_validator(mode="before")` accepting comma-separated **or** JSON-array values; defaults to `http://localhost:3000`, `http://localhost:5173`.
- Appended `ALLOWED_ORIGINS=...` to root `.env` and `backend/.env.example`.
- New tests: `backend/tests/test_cors.py` (allowed preflight, disallowed origin, never `"*"`, both parse formats).

### Group 5 — Cleanup
- **B1** `datetime.utcnow()` → `datetime.now(UTC)` everywhere (`db/models.py` via a local `utcnow()` helper for 11 columns; `endpoints/auth.py`, `endpoints/user.py`, `services/chat_indexer.py`, `services/fact_persistence.py`, and 3 test files). Deprecation warnings dropped 164 → 5.
- **B2** 13 `print()` → module `logger.warning/error` (`metrics.py`, `user.py` ×2, `hybrid_search.py`, `intent_router.py`, `loader.py` ×4, `retriever.py` ×4).
- **B3** `import fitz` → `import pymupdf as fitz` (4 sites).
- **B4** Pydantic `class Config` → `model_config = ConfigDict(from_attributes=True)` (3 sites).
- **E8** duplicate `SHOW_SPECIALIST_CONTACTS` removed.
- **E5/E6** docs URL gated on `DEBUG`; failed login now `401`.
- **F8** unused icon imports removed (`Calendar` in `Profile.jsx`; `Users` in `PatientContextSelector.jsx`; `HeartPulse` in `ChatWindow.jsx`; `Briefcase/Ruler/Salad/Flame` in `HealthProfile.jsx`).
- **F9/F12** new `services/logger.js` (dev-only, no-ops in production); `console.*` routed through it; `speech.js` `alert()` replaced by graceful no-op.
- Dead exports removed from `api.js`: `checkBackendHealth`, `getChatDocuments`, `attachChatDocument`, `updateUser`.

---

## 4. Features: Removed / Wired / Intentionally Unwired

**Removed**
- "Sign out of all devices" (was fake; called single logout).
- Dead frontend exports (`checkBackendHealth`, `getChatDocuments`, `attachChatDocument`, `updateUser`).
- Deprecated import patterns and duplicate config symbol.

**Newly wired (functional)**
- Logout (UI + full local-state/auth cleanup + redirect + global reset).
- Theme preference incl. `system` (persisted raw).
- Language preference (persisted to profile).
- Change-password (verified end-to-end).
- Memory consent toggle (existing endpoint, now covered by tests).

**Intentionally left disabled (with UX affordance)**
- **Change email** — disabled, tooltip: *"Coming soon — contact support to change your email"*.
- **Privacy policy** — disabled button + *"Coming soon"* badge, tooltip: *"Policy coming soon"*.
- **Export my data** — remains disabled (by design).

---

## 5. Logout Flow — Before vs. After

**Before**
1. No reachable logout control anywhere (Critical).
2. `logout()` cleared only a handful of keys → stale `mediskye_*` state leaked across sessions.
3. No global state reset; conversations could persist after sign-out.
4. Consent-prompt flag stayed set.

**After**
1. Sidebar footer **Log out** → confirmation modal *"Log out of MediSkye?"*.
2. `clearLocalAuthStorage()` removes `token`, all `mediskye_*` localStorage keys, and the `mediskye_consent_prompted` sessionStorage flag — while preserving unrelated keys.
3. `handleLogout` resets conversations / active document / patient context, then `navigate('/login', { replace: true })`.
4. Backend blocklists the JWT via `POST /logout`.
5. Covered by `frontend/src/test/logout.test.jsx` and `backend/tests/test_logout.py`.

---

## 6. Test Counts

| Suite | Baseline | Final |
|---|---|---|
| Backend (`pytest tests -q`) | 58 passed / 164 warnings | **71 passed / 5 warnings** |
| Frontend (`npm test`) | 28 passed (6 files) | **39 passed (8 files)** |
| Frontend build (`npm run build`) | — | **✅ 1861 modules, built OK** |

New test files: `test_logout.py`, `test_memory_consent.py`, `test_dependent_create.py`, `test_token_expiry.py`, `test_cors.py`, `logout.test.jsx`, `ChatApp.test.jsx`.

---

## 7. Files Changed

### Backend — modified
`app/api/v1/endpoints/auth.py`, `app/api/v1/endpoints/metrics.py`, `app/api/v1/endpoints/user.py`, `app/core/auth.py`, `app/core/config.py`, `app/db/models.py`, `app/main.py`, `app/rag/hybrid_search.py`, `app/rag/intent_router.py`, `app/rag/loader.py`, `app/rag/retriever.py`, `app/schemas/dependent.py`, `app/schemas/user.py`, `app/services/chat_indexer.py`, `app/services/fact_persistence.py`, `app/services/pdf_service.py`, `.env.example`, `tests/test_facts_api.py`, `tests/test_multi_document.py`, `tests/test_upload.py`

### Backend — created
`tests/test_logout.py`, `tests/test_memory_consent.py`, `tests/test_dependent_create.py`, `tests/test_token_expiry.py`, `tests/test_cors.py`

### Frontend — modified
`src/services/api.js`, `src/services/speech.js`, `src/components/ChatApp.jsx`, `src/components/ChatWindow.jsx`, `src/components/HealthProfile.jsx`, `src/components/PatientContextSelector.jsx`, `src/components/Profile.jsx`, `src/components/SettingsModal.jsx`, `src/components/Sidebar.jsx`, `src/test/ChatMessage.test.jsx`, `src/test/HealthProfile.test.jsx`, `src/test/SettingsModal.test.jsx`, `src/test/Sidebar.test.jsx`

### Frontend — created
`src/services/logger.js`, `src/test/logout.test.jsx`, `src/test/ChatApp.test.jsx`

### Repository root
`.env` (added `ALLOWED_ORIGINS`)

---

## 8. Manual Verification Checklist

- [ ] Sign in, open the sidebar, click **Log out**, confirm the modal, and verify redirect to `/login`.
- [ ] Inspect `localStorage`/`sessionStorage` after logout — no `mediskye_*` or `token` keys remain; unrelated keys survive.
- [ ] Sign back in and confirm conversations/active document/patient context start clean.
- [ ] Settings → toggle theme through Light/Dark/System; reload; the choice (incl. System) persists.
- [ ] Settings → change language; reload; the language persists.
- [ ] Settings → change password; confirm success toast and that the old password no longer works (401 on login).
- [ ] Settings → toggle memory consent; confirm server state via memory status.
- [ ] Settings → "Change email" shows the "Coming soon — contact support" tooltip; "Privacy policy" shows "Coming soon".
- [ ] Settings → confirm "Sign out of all devices" is gone.
- [ ] Generate an answer, click **Regenerate** — no duplicate user bubble; only the assistant answer is replaced.
- [ ] Send a query and click **Stop** — the request aborts and the UI returns to idle without an error toast.
- [ ] Detach a document in a multi-document chat — the next document becomes active; no console errors.
- [ ] Re-save an unchanged weight in Health Profile — no duplicate fact is created.
- [ ] Upload a PDF (text + scanned) and confirm extraction still works (verifies the `pymupdf` rename).
- [ ] Confirm `/docs` is available in DEBUG and disabled in production.
- [ ] Verify a cross-origin request from a disallowed origin is rejected (no `Access-Control-Allow-Origin`).
- [ ] Run `./.venv/Scripts/pytest.exe tests -q` → expect **71 passed**.
- [ ] Run `npm test` → expect **39 passed**; `npm run build` → succeeds.

---

## 9. Deferred / Documented (out of scope, no Phase 0 touch)

- L4 `ProtectedRoute` validates presence only; L5 dead blocklist branch; L6 in-process `MockRedis`.
- E3 `delete_user_me` audit-log retention behavior (deliberate).
- D2 missing FK `ondelete CASCADE`; D3 partially addressed; D4 `create_all` in dev.
- F6, F7 (hardcoded `API_BASE`), F10, F11, F13, F14 (idiomatic `import React`).
- B6 broad `except` blocks; B7/B8 minor duplication.
- T5/T6/T7 coverage gaps.

*No commits or pushes were made. Phase 0 security code was not modified.*
