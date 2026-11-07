# MediSkye Frontend Redesign — Changelog & Integration Guide

**Scope:** complete presentation-layer redesign of `frontend/` ("Clinical Obsidian" design system, desktop split-pane workbench, Android-first mobile shell, new clinical visualizations).
**Backend contract:** unchanged. Every existing `services/api.js` function keeps its exact signature and behavior. One optional, additive function was added (`getMetricTrends`) with a client-side fallback.
**Test status at hand-off:** `npm test` → **27 files, 195 tests, all passing** (178 original + 17 new). `npm run build` → passes.

---

## Section 1: Architecture & File Inventory

### 1.1 New files created

| Path | Purpose |
|---|---|
| `src/lib/cn.js` | `cn(...)` = `clsx` + `tailwind-merge` for conflict-free class composition. |
| `src/lib/clinical.js` | Pure clinical computation layer over the existing `lab_metrics` rows: numeric/range/date parsing, status classification (`critical/high/low/borderline/normal/unknown`), semantic tone mapping (rose/amber/emerald), reference-interval geometry for range bars, Δ% computation (`delta_pct` or derived from `previous_value`), ≥10 % notable-shift / drop detection, organ-system grouping, triage summary, flagged-first sort, filters, longitudinal trend-series builder. No network access. |
| `src/lib/storageKeys.js` | Single registry of every `localStorage` / `sessionStorage` key + safe `readStorage` / `writeStorage` helpers. |
| `src/hooks/useViewport.js` | `isDesktop (≥1024)`, `isTablet (768–1023)`, `isMobile (<768)` from `window.innerWidth` (deterministic in JSDOM). |
| `src/hooks/useHotkeys.js` | Global keyboard shortcut registry (`mod` = Ctrl on Windows/Android/Linux, ⌘ on macOS). Exports `MOD_LABEL`. |
| `src/hooks/useResizablePane.js` | Pointer + keyboard resizable inspector pane (persisted width, re-clamped to always leave ≥420 px for the chat column). |
| `src/hooks/useLabMetrics.js` | Lazy, de-duplicated, module-cached `fetchLabMetrics(docId)`; exports `loadMetricsFor` and `invalidateMetrics`. |
| `src/hooks/useTrendData.js` | Longitudinal series: tries `GET /users/me/metrics/trends`, falls back to fetching `/extract-metrics` for up to 8 recent reports (concurrency 3) and merging client-side. |
| `src/components/ui/IconButton.jsx` | Accessible icon button (label → `aria-label` + `title`), 36 px / 44 px (coarse pointer) hit area. |
| `src/components/ui/Kbd.jsx` | Keyboard key chip. |
| `src/components/ui/SegmentedControl.jsx` | Pill segmented control with spring-animated active indicator (framer-motion `layoutId`). |
| `src/components/ui/Sheet.jsx` | Responsive sheet: **vaul** bottom sheet with drag-to-dismiss on `<768px`; Radix Dialog side panel / centered dialog on `≥768px`. Focus trap, Esc, `aria-modal`. |
| `src/components/clinical/StatusPill.jsx` | Status pill with direction glyph + text (`↑ High`, `↓ Low`, `▲ Critical`, `↘ Notable Drop…`, `✓ Normal`). |
| `src/components/clinical/RangeBar.jsx` | Reference-interval bar: emerald band = interval, marker = value (tone-colored), hollow ring + stroke = previous value. `role="img"` with a full-sentence label. |
| `src/components/clinical/DeltaIndicator.jsx` | `44.0 → 24.0 ng/mL ↓ 45.5%` readout, amber when \|Δ\| ≥ 10 %. |
| `src/components/clinical/TrendChart.jsx` | Dependency-free SVG trend chart (reference band, hover/focus tooltips, dashed baseline points) + `Sparkline`. Renders at real container pixel width (ResizeObserver). |
| `src/components/clinical/TrendsView.jsx` | Longitudinal explorer: ranked biomarker list with sparklines + focused chart. |
| `src/components/clinical/OrganSystemsOverview.jsx` | Triage summary (distribution bar, quick filters *All / Flagged only / Notable drops*) + organ-system cards (Hematology & Iron, Renal & Electrolytes, Hepatic, Lipids, Thyroid & Vitamins, Metabolic & Glycemic, Inflammation, Other). |
| `src/components/workbench/Workbench.jsx` | The clinical workbench: header, conversation column (ChatWindow + UploadStepper + ChatInput + drag-and-drop), resizable desktop inspector, mobile analytic views, mobile "More actions" sheet, 1-click physician print flow (moved here from the old ChatWindow). |
| `src/components/workbench/InspectorPanel.jsx` | Inspector with four lenses: **Overview** (triage), **Metrics** (LabMetrics), **Trends**, **Report** (specimen/source details + print/export actions). Used as desktop pane and mobile full-screen view. |
| `src/components/workbench/NavRail.jsx` | 56 px desktop rail shown while the history sidebar is collapsed. |
| `src/components/workbench/PatientSwitcher.jsx` | Caregiver patient switcher (Self + dependents, avatars, report counts). Desktop popover / mobile bottom sheet. Also exports `PatientAvatar`, `buildPatients`, `isSelfSelected`, `initialsOf`. Replaces `PatientContextSelector.jsx`. |
| `src/components/workbench/CommandPalette.jsx` | `Ctrl/⌘ + K` palette (cmdk): actions, patients, biomarkers in the open report, reports, conversations, language toggle, "Ask MediSkye: …". |
| `src/components/workbench/MemoryVault.jsx` | Patient Memory Vault sheet: consent toggle, search, category chips, month-grouped timeline, source-report badges, per-fact delete, typed-confirmation clear-all. Scoped to the selected patient. |
| `src/components/workbench/UploadStepper.jsx` | Two-phase pipeline stepper: *Validating PDF → Extracting clinical text → Building hybrid FAISS + BM25 index → Ready for Q&A* + "Warming summary cache" badge. |
| `src/components/workbench/Brand.jsx` | `BrandMark` (ECG trace across a reference band) and `BrandLockup`. |
| `src/components/auth/AuthShell.jsx` | Split auth layout (product panel ≥1024 px, form card right). Wraps Login and Register. |
| `src/test/clinical.test.js` | 11 unit tests for `lib/clinical.js`. |
| `src/test/WorkbenchComponents.test.jsx` | 6 tests for UploadStepper, RangeBar, LabMetrics filters/Ask, OrganSystemsOverview. |
| `REDESIGN_CHANGELOG.md` | This document. |

### 1.2 Modified files

| Path | Summary of changes |
|---|---|
| `package.json` / `package-lock.json` | New dependencies (Section 2). Scripts unchanged. |
| `index.html` | `viewport-fit=cover, interactive-widget=resizes-content` (Android keyboard), new theme color `#05070b`, meta description, SVG favicon. Removed Google Fonts `<link>`s (fonts are now self-hosted). |
| `tailwind.config.js` | Design tokens: surface ladder (`obsidian`, `carbon`, `graphite`, `slate2`, `ridge`), text (`ink`, `ink-soft`, `ink-mute`, `ink-faint`), `clinical.*` accents, `font-display` (Fraunces) / `font-mono` (JetBrains Mono) / `font-sans` (Inter), `shadow-specular/float/glow`, `animate-token-pulse`, `animate-stage-sweep`. `brand.*` palette kept. |
| `vite.config.js` | Two new manual chunks: `vendor-motion` (framer-motion) and `vendor-ui` (cmdk, vaul, @radix-ui). Proxy, Sentry and sourcemaps unchanged. |
| `src/main.jsx` | Imports self-hosted variable fonts; branded crash fallback for the Sentry ErrorBoundary. |
| `src/index.css` | Rewritten design-system base: CSS variables, Windows-grade thin scrollbars (`::-webkit-scrollbar` + `scrollbar-width: thin`), forced antialiasing, `:focus-visible` ring, 16 px mobile inputs (no zoom), `.ms-glass/.ms-surface/.ms-raised/.ms-num/.ms-display/.ms-tap`, `.ms-table-card` (rounded horizontal-scroll cards with **sticky first column**), `h-app`/`min-h-app` (100dvh), safe-area utilities, cmdk/vaul hooks, all previous keyframes. Auth `.login-*` classes kept (restyled, dark-only). Print rules for `#print-summary` / `#print-transcript` kept verbatim. |
| `src/styles/print.css` | Adds `div[class*="h-app"]` to the ancestor reset list; keeps fills of the new print range-position bars (`print-color-adjust: exact`). |
| `src/services/api.js` | **Additive only:** `getMetricTrends(patientId, { signal })`. No existing function touched. |
| `src/App.jsx` | Loading skeleton retoned to the new palette. Routes / ProtectedRoute / auth listener unchanged. |
| `src/components/ChatApp.jsx` | All state & handler logic preserved (upload polling, SSE streaming, 409 handling, rename/delete, history sync). Added: structured `uploadState` for the stepper, inspector state, metrics/trend hooks, keyboard shortcuts, command palette, memory vault, patient-scoped report list, new layout (sidebar drawer + desktop NavRail + Workbench). Sidebar now defaults **closed below 1024 px** (was 768 px). |
| `src/components/ChatWindow.jsx` | Now only the message stream + empty state. Header, view switcher, metrics loading and print flow moved to `Workbench.jsx`. Context-aware suggestions built from the report's actual flagged biomarkers. Stick-to-bottom scrolling. |
| `src/components/ChatInput.jsx` | Redesigned composer (glass card, 40 px targets, `enterKeyHint="send"`, IME-safe Enter). Imperative handle adds `focus()` and `insertText(value)`; `openFileUpload()` preserved. New optional `hidden` prop. File input value reset after selection (re-upload same file). |
| `src/components/ChatMessage.jsx` | New typography, brand avatar, streaming caret pulse. Markdown tables render inside `.ms-table-card` with a sticky first column on **all** viewports (the old mobile duplicate-card rendering is gone). Status / Δ% cells are auto-toned. All titles/aria-labels preserved. |
| `src/components/LabMetrics.jsx` | Rebuilt: inline range bars in the *Reference Range* column, quick-filter chips, organ-system grouping toggle, Clinical Biomarker Cards on mobile, `Ask` action per biomarker, controlled/uncontrolled search & filter, `layout` prop. Column headers, empty-state copy, sort contract and `.block.sm:hidden` mobile container preserved. |
| `src/components/Sidebar.jsx` | Restyled; history split into *Lab reports* and *History*; dependent avatar on dependent chats; Memory vault entry; palette button; collapse button. All test contracts preserved (see §6). |
| `src/components/PrintableSummary.jsx` | Adds a *Position* column (paper-safe range bar) to the flagged table and formats Δ as `↓ 45.5% (-20.0 ng/mL)`. Section headings/text unchanged. |
| `src/components/Login.jsx`, `Register.jsx` | Only the outer wrapper changed: `<div className="login-page">…<div className="login-card …">` → `<AuthShell><div className="login-card">`. **No logic, handler, Firebase or copy changes.** |
| `src/components/SettingsModal.jsx`, `Profile.jsx`, `HealthProfile.jsx`, `ExportModal.jsx`, `ConfirmModal.jsx`, `MemoryConsentModal.jsx`, `DocumentModal.jsx`, `AuthAction.jsx`, `PrivacyPolicy.jsx` | Visual only: design-token swap (zinc → ink/graphite/carbon), modals become **bottom sheets on mobile** (`items-end`, `rounded-t-[28px]`, `max-h-[94dvh]`, safe-area padding), cyan primary buttons, removed all-caps labels. `useFocusTrap` usage, handlers, aria-labels and copy unchanged. ConfirmModal z-index raised to `z-[80]` so it always sits above sheets. |
| `src/components/LandingPage.jsx` | New nav + hero (live "workbench preview" with real RangeBar/StatusPill components). Deferred-section loading, scroll-spy, auth redirect and all tested copy preserved. |
| `src/components/landing/shared.jsx` + section files | Palette/typography retuned to the design system (Fraunces + Inter), no structural changes. |
| `src/locales/en/translation.json`, `hi/translation.json` | New `workbench.*` namespace (31 keys, English + Hindi). Existing keys untouched. |
| `src/test/SidebarRename.test.jsx` | One assertion updated: rename-input class list now checks design tokens (`bg-graphite`, `border-cyan-500/40`, `px-2.5`, `rounded-lg`) instead of `bg-gray-800`/`border-gray-600`/`focus:border-blue-500`. Behavioral assertions unchanged. |

### 1.3 Deleted / deprecated

| Path | Replacement |
|---|---|
| `src/components/PatientContextSelector.jsx` | `src/components/workbench/PatientSwitcher.jsx` (same `aria-label="Select patient context"`, same `onSelectPatient(id)` / `onOpenDependents()` callbacks). |
| `src/components/RagSourcesPanel.jsx` | Unchanged stub (`return null`), still unused. Safe to delete. |
| Google Fonts (Figtree / Newsreader / Inter CDN) | Self-hosted `@fontsource-variable/*` packages. |

### 1.4 Updated directory tree (`frontend/src/`)

```
src/
├── App.jsx
├── main.jsx
├── i18n.js
├── instrument.js
├── index.css                      ← design system
├── styles/print.css
├── lib/
│   ├── clinical.js                ← NEW clinical computation layer
│   ├── cn.js                      ← NEW
│   └── storageKeys.js             ← NEW
├── hooks/
│   ├── useFocusTrap.js
│   ├── useIntersectionObserver.js
│   ├── useHotkeys.js              ← NEW
│   ├── useLabMetrics.js           ← NEW
│   ├── useResizablePane.js        ← NEW
│   ├── useTrendData.js            ← NEW
│   └── useViewport.js             ← NEW
├── services/                      (api.js +getMetricTrends; others untouched)
│   ├── api.js · firebase.js · logger.js · speech.js · storage.js
├── locales/{en,hi}/translation.json
├── components/
│   ├── ChatApp.jsx                ← state container + layout
│   ├── ChatWindow.jsx · ChatInput.jsx · ChatMessage.jsx
│   ├── LabMetrics.jsx · PrintableSummary.jsx · PrintableTranscript.jsx
│   ├── Sidebar.jsx · SettingsModal.jsx · Profile.jsx · HealthProfile.jsx
│   ├── ExportModal.jsx · ConfirmModal.jsx · MemoryConsentModal.jsx · DocumentModal.jsx
│   ├── Login.jsx · Register.jsx · AuthAction.jsx · PrivacyPolicy.jsx · LandingPage.jsx
│   ├── RagSourcesPanel.jsx        (unused stub)
│   ├── auth/AuthShell.jsx         ← NEW
│   ├── clinical/                  ← NEW
│   │   ├── DeltaIndicator.jsx · OrganSystemsOverview.jsx · RangeBar.jsx
│   │   └── StatusPill.jsx · TrendChart.jsx · TrendsView.jsx
│   ├── ui/                        ← NEW
│   │   └── IconButton.jsx · Kbd.jsx · SegmentedControl.jsx · Sheet.jsx
│   ├── workbench/                 ← NEW
│   │   ├── Brand.jsx · CommandPalette.jsx · InspectorPanel.jsx · MemoryVault.jsx
│   │   └── NavRail.jsx · PatientSwitcher.jsx · UploadStepper.jsx · Workbench.jsx
│   └── landing/ (CTASection · FeaturesSection · FooterSection · HowItWorksSection · SafetySection · shared)
└── test/  (25 original files + clinical.test.js + WorkbenchComponents.test.jsx)
```

---

## Section 2: Dependencies & Build Configuration

### 2.1 Install command

```bash
cd frontend
npm install framer-motion@^11.18.2 cmdk@^1.1.1 vaul@^1.1.2 @radix-ui/react-dialog@^1.3.1 \
  clsx@^2.1.1 tailwind-merge@^2.6.1 \
  @fontsource-variable/inter@^5.3.0 @fontsource-variable/fraunces@^5.3.0 @fontsource-variable/jetbrains-mono@^5.3.0
```

(`package.json` and `package-lock.json` already contain these; a plain `npm ci` is enough.)

| Package | Why |
|---|---|
| `framer-motion@^11` | Spring layout transitions (segmented controls, inspector tabs), popover enter/exit. v11 chosen for React 18 support. |
| `cmdk@^1` | Accessible, fuzzy-filtered command palette primitive. |
| `vaul@^1` | Native-feeling Android/iOS bottom sheets with drag-to-dismiss. |
| `@radix-ui/react-dialog@^1.3.1` | Desktop sheets/palette dialog (focus trap, scroll lock, `aria-modal`). Same version vaul depends on, pinned explicitly so we don't import a transitive dependency. |
| `clsx` + `tailwind-merge@^2` | Conditional classes without utility conflicts. **v2 is required for Tailwind 3** (v3 targets Tailwind 4). |
| `@fontsource-variable/{inter,fraunces,jetbrains-mono}` | Self-hosted variable fonts: no third-party font requests from a PHI app, works under strict CSP, no FOUT from Google Fonts. |

Not added on purpose: **recharts/@visx** — trend charts are ~150 lines of SVG, saving ~100 KB gz. **Zustand** — state stays in `ChatApp` (tests mount `ChatApp` directly).

### 2.2 Config changes

- `tailwind.config.js` — tokens listed in §1.2. Existing `darkMode: 'class'`, typography plugin and `brand` palette kept.
- `postcss.config.js` — unchanged.
- `vite.config.js` — added `vendor-motion` and `vendor-ui` manual chunks. Current output: `ChatApp` 62.7 KB gz, `vendor-motion` 38 KB gz, `vendor-ui` 22.6 KB gz.
- `index.css` — see §1.2. Mobile inputs are forced to `font-size: 16px !important` under 767 px to prevent Android/iOS focus zoom.
- `vitest.config.js` — unchanged.

---

## Section 3: Backend API Contract & `services/api.js` Mapping

### 3.1 Preserved API calls (unchanged signatures, unchanged call sites unless noted)

| Function | Called from | Notes |
|---|---|---|
| `uploadPdfReport(file, patientId, chatId, customTitle?)` | `ChatApp.handleAttachFile` | Still called with exactly `(file, selectedPatientId, sessionId)` or `+ customTitle` for samples. |
| `getUploadStatus(jobId, 10000)` | `ChatApp.handleAttachFile` polling loop | Same cadence (500/500/1000/1000 ms then 2 s; `window.__POLL_INTERVAL__` / `__UPLOAD_MAX_WAIT__` test hooks kept). The response's optional `stage` / `phase` / `index_status` fields are now read to drive the stepper (see §3.3). |
| `sendQueryStream(query, docId, language, onChunk, patientId, signal)` | `ChatApp.handleSendMessage` | Same chunk handling (`chunk`/`token`, `stage`+`message`, `specialists`, `error`, `title`). |
| `getUserDocuments()` / `getGeneralChats()` / `getDocumentChats(docId, sessionId)` | `ChatApp.refreshDocuments` / `loadChatHistory` | Unchanged. No new callers (call counts asserted by tests are identical). |
| `renameDocument`, `renameChatSession`, `deleteDocument`, `deleteChatSession`, `clearAllChatSessions` | `ChatApp` handlers | Unchanged. |
| `getProfile`, `getDependents`, `updateProfile`, `deleteAccount`, `logout` | `ChatApp`, `Workbench` (print fallback `getProfile`) | Unchanged. |
| `fetchLabMetrics(documentId, forceRefresh)` | **Moved** from `ChatWindow` to `hooks/useLabMetrics.js` | Called lazily when the inspector / mobile analytics view / command palette is open, de-duplicated per document, plus `forceRefresh=true` from the inspector's "Re-run biomarker extraction" button. |
| `getDocumentSummary(documentId)` | `ChatApp.handleExportSummary` | Unchanged; triggered by the header *Export Summary* button, the Report tab, `Ctrl+Shift+P`, or the palette. |
| `getFacts(dependentId)` / `getMemoryFacts` | `SettingsModal` (unchanged), **new** `MemoryVault` | Vault passes the selected patient id (`'self'` → no query param). |
| `deleteFact(factId)` | **new** `MemoryVault` | |
| `clearAllMemoryFacts(dependentId)` | `SettingsModal` (unchanged), **new** `MemoryVault` (patient-scoped) | |
| `updateMemoryConsent(consent)` (fallback `updateProfile`) | `SettingsModal`, **new** `MemoryVault` | |
| `exportDocumentData`, `exportUserAccountData` | `ExportModal`, `SettingsModal` | Unchanged. |
| `getDependents`, `createDependent`, `updateDependent`, `deleteDependent` | `Profile` | Unchanged. |
| `login`, `register`, `sendCustomVerification`, `sendCustomPasswordReset`, `api.*` | Auth screens | Unchanged. |

### 3.2 Modified API signatures

**None.** One function was **added**:

```js
// Before: (did not exist)
// After:
export async function getMetricTrends(patientId = null, options = {})  // → Promise<TrendsPayload | null>
```

It never throws and never dispatches `auth:expired`; any non-2xx, network error or unexpected payload returns `null`, which triggers the client-side fallback.

### 3.3 New backend endpoints requested (optional enhancements)

#### A. `GET /users/me/metrics/trends`

1. **Method & path:** `GET /users/me/metrics/trends`
2. **Query:** `patient_id` *(optional, string)* — dependent id; omit for Self. Optional extension: `limit` (reports, default 8), `keys` (comma-separated biomarker keys).
3. **Response (200):**
```json
{
  "patient_id": "self",
  "generated_at": "2026-11-07T08:30:00Z",
  "reports": [
    { "document_id": "aaaa-…", "title": "CBC & Iron Follow-up", "collected_at": "2026-11-04" },
    { "document_id": "bbbb-…", "title": "Baseline Panel", "collected_at": "2026-10-24" }
  ],
  "series": [
    {
      "key": "hemoglobin",
      "name": "Hemoglobin",
      "unit": "g/dL",
      "reference_range": "12.0–15.5",
      "points": [
        { "document_id": "bbbb-…", "collected_at": "2026-10-24", "value": 13.1, "raw_value": "13.1", "status": "Normal" },
        { "document_id": "aaaa-…", "collected_at": "2026-11-04", "value": 11.6, "raw_value": "11.6", "status": "Low" }
      ]
    }
  ]
}
```
   `key` should be the normalized biomarker name (lowercase alphanumerics, parenthetical text removed — mirror `normalizeName()` in `lib/clinical.js`). `value` must be numeric; non-numeric readings can be omitted. `collected_at` accepts ISO date or the same display strings `/extract-metrics` returns.
4. **Fallback today:** `useTrendData` fetches `POST /extract-metrics` for up to 8 of the patient's most recent reports (3 in parallel, cache shared with the inspector) and merges them with `buildTrendSeries()`. With a single report it still draws baseline → follow-up from `previous_value` / `previous_date`. The Trends tab footer shows which source was used.

#### B. Upload pipeline stage on `GET /upload/status/{job_id}` (additive field)

1. **Method & path:** existing `GET /upload/status/{job_id}`
2. **Request:** unchanged.
3. **Response:** add `"stage": "validating" | "extracting" | "indexing" | "ready"` alongside the existing `status`:
```json
{ "job_id": "job-123", "status": "processing", "stage": "indexing", "index_status": "building" }
```
4. **Fallback today:** first `processing` poll → *Extracting clinical text*, later polls → *Building hybrid FAISS + BM25 index*; `index_status` presence also maps to indexing. `completed` → *Ready for Q&A* + a 6 s "Warming summary cache" badge (Step B runs server-side). Recognized substrings: `valid|queue|pending`, `extract|ocr|pars|text`, `index|embed|faiss|bm25|vector`.

#### C. (Optional) Memory fact provenance

`GET /users/me/facts` items may include `source_document_id` (or `document_id`). When present, the Memory Vault renders the source report title as a badge; otherwise it falls back to `source_type` ("From a lab report" / "From a conversation").

---

## Section 4: State Management, Context & Storage Keys

### 4.1 State containers

No React Context or external store was introduced. `ChatApp` remains the single state owner (tests mount it directly).

| Owner | State | Notes |
|---|---|---|
| `ChatApp` (existing) | `sessionId`, `conversations`, `activePdf`, `currentUser`, `dependents`, `selectedPatientId`, `language`, `viewMode`, `isGenerating`, `uploadProgress`, `uploadError`, modal flags, `autoRead`, `sidebarOpen` | Unchanged semantics. `viewMode` now takes `'chat' \| 'metrics' \| 'analytics'` (mobile/tablet only). |
| `ChatApp` (new) | `uploadState` `{ phase, fileName, startedAt, finishedAt, warming, error }` | Drives `UploadStepper`. Auto-clears 9 s after success. |
| `ChatApp` (new) | `inspectorOpen`, `inspectorTab` (`overview/metrics/trends/report`), `metricsFilter` (`all/flagged/drops`), `metricsSearch`, `highlightKey` | Inspector + cross-component biomarker focus (palette → inspector, overview → metrics). |
| `ChatApp` (new) | `paletteOpen`, `memoryOpen`, `printSignal` (counter) | `printSignal` lets the palette / `Ctrl+Shift+P` trigger the Workbench print flow. |
| `useLabMetrics(docId, {enabled})` | `{ metrics, loading, loaded, reload(), ensure() }` | Module-level Promise cache per document id (`invalidateMetrics(docId)` to bust). Empty results are not pinned (backend may still be warming). |
| `useTrendData({patientId, reports, enabled})` | `{ series: Map, loading, source: 'server' \| 'client', reportCount }` | |
| `useResizablePane` | `{ width, isDragging, handleProps, reset }` | |
| `useViewport` | `{ width, height, isDesktop, isTablet, isMobile }` | |
| `Workbench` (local) | `showPrintSummary`, `printMetrics`, `printUser`, `moreOpen`, `dragActive` | |

### 4.2 Storage keys

| Key | Store | R/W | Status | Purpose |
|---|---|---|---|---|
| `token` | localStorage | R/W | preserved | Auth JWT (api.js, ProtectedRoute). |
| `mediskye_ui_lang` | localStorage | R/W | preserved | i18next language (`en`/`hi`). Now also written by the palette / mobile language toggle. |
| `mediskye_patient_id` | localStorage | R/W | preserved | Selected patient (`'self'` or dependent id). |
| `mediskye_auto_read` | localStorage | R/W | preserved | Auto-read answers. |
| `mediskye_sidebar_open` | localStorage | R/W | preserved | Desktop sidebar preference (ignored below 1024 px where the sidebar is a drawer). |
| `mediskye_theme`, `theme` | localStorage | W | preserved | Always `dark`. |
| `mediskye_inspector_open` | localStorage | R/W | **new** | Desktop inspector open state. Default when unset: open on ≥1280 px, closed below. |
| `mediskye_inspector_width` | localStorage | R/W | **new** | Inspector width in px (340–760). |
| `mediskye_inspector_tab` | localStorage | R/W | **new** | Last inspector tab. |
| `mediskye_consent_prompted` | sessionStorage | R/W | preserved | Memory-consent prompt shown this session. |
| `mediskye_conversations`, `mediskye_session_id`, `mediskye_last_active_user` | localStorage | delete | preserved | Legacy caches still purged on mount. |

All new keys are `mediskye_`-prefixed, so `clearLocalAuthStorage()` removes them on logout. Note (pre-existing behavior, not changed): `PRESERVED_STORAGE_KEYS` lists `mediskye_language`, but i18n writes `mediskye_ui_lang`, so the UI language resets on logout. If you want it to persist, add `'mediskye_ui_lang'` to that set in `api.js`.

---

## Section 5: Component Prop & Event Wiring Guide (for Antigravity)

### 5.1 Checklist

1. `npm ci` (lockfile already updated) → `npm test` (expect 195 passing) → `npm run build`.
2. **No backend changes are required.** Optionally implement §3.3-A and §3.3-B; the UI picks them up automatically.
3. `ChatApp` still takes **no props** and is still the `/chat/*` route element. `App.jsx` routes are unchanged.
4. `handleAttachFile(file, { customTitle } = {})` — unchanged signature and return value (`newDocId | null`). It is now reachable from: composer paperclip, drag-and-drop on the conversation column, NavRail upload, palette "Upload a lab report", `Ctrl+U`, inspector empty states (all via `chatInputRef.current.openFileUpload()` or a direct call).
5. `handleSendMessage(query, { appendUserMessage, docIdOverride, preserveTitle })` — unchanged. New callers: biomarker **Ask** buttons (`handleAskAbout(row)` builds a grounded question) and palette "Ask MediSkye: …".
6. `handlePatientSelect(patientId)` — unchanged; now invoked by `PatientSwitcher` (header) and the palette. `onSelectDocument` does not exist in this codebase; report selection is `handleSelectChat(id)` (sidebar, palette).
7. The print flow moved from `ChatWindow` to `Workbench.handlePrintDoctorSummary()`; it still calls `onExportSummary` (= `ChatApp.handleExportSummary` → `getDocumentSummary`), mounts `PrintableSummary`, sets `document.title`, then `window.print()` after 150 ms and unmounts on `afterprint`.
8. Auth: `Login.jsx` / `Register.jsx` / `firebase.js` logic is untouched; only the wrapper is `<AuthShell>`. `AuthAction.jsx` is restyled only.

### 5.2 Component prop changes

| Component | Removed / ignored props | Added props |
|---|---|---|
| `ChatWindow` | `viewMode`, `onViewModeChange`, `toggleSidebar`, `dependents`, `selectedPatientId`, `onSelectPatient`, `onOpenDependents`, `onOpenUpload`, `documentId`, `isExportingSummary`, `printSummaryText`, `onExportSummary`, `onOpenExport`, `darkMode` (all moved to `Workbench`) | `patientName`, `metrics` (for grounded suggestions), `className` |
| `ChatInput` | `darkMode`, `currentUser`, `dependents`, `selectedPatientId`, `onSelectPatient`, `onOpenDependents` (were already unused) | `hidden?: boolean`, `showKeyboardHint?: boolean`; ref adds `focus()`, `insertText(text)` |
| `ChatMessage` | `darkMode` (ignored) | — |
| `Sidebar` | `darkMode`, `setDarkMode`, `language`, `setLanguage` ignored (accepted, harmless) | `onOpenMemory?`, `onOpenPalette?`, `dependents?` |
| `LabMetrics` | `darkMode` (ignored), `onBack` (accepted, unused) | `layout: 'auto'\|'list'\|'table'`, `search`/`onSearchChange`, `filter`/`onFilterChange`, `onAskAbout(row)`, `highlightKey`, `showHeader` |
| `PatientContextSelector` | **deleted** | Use `PatientSwitcher` with `currentUser, dependents, selectedPatientId, onSelectPatient(id), onOpenDependents(), reportCounts?` |
| `PrintableSummary` | — | — (same props) |

### 5.3 Keyboard shortcuts (desktop)

| Shortcut | Action |
|---|---|
| `Ctrl/⌘ + K` | Command palette |
| `Ctrl/⌘ + B` | Toggle history sidebar |
| `Ctrl/⌘ + \` | Toggle clinical inspector (report open) |
| `Alt + 1…4` | Inspector tab: Overview / Metrics / Trends / Report |
| `Ctrl/⌘ + U` | Upload a report |
| `Ctrl/⌘ + Shift + O` | New conversation |
| `Ctrl/⌘ + Shift + P` | Print physician summary |
| `Ctrl/⌘ + Shift + M` | Memory vault |
| `Ctrl/⌘ + ,` | Settings |
| `/` | Focus the composer (when not typing) |
| `←` / `→`, `Home` / `End` on the pane divider | Resize inspector; double-click resets |

### 5.4 Responsive behavior

- **≥1280 px:** sidebar (272 px) + chat + inspector (default 440 px, resizable 340–760).
- **1024–1279 px:** opening the inspector folds the sidebar into the 56 px NavRail (transient, not persisted).
- **768–1023 px (tablet) and <768 px (phone):** single pane; sidebar is an overlay drawer; with a report open a segmented control switches **Chat / Lab Metrics / Insights**. The composer is hidden on Lab Metrics and Insights. Header overflow actions live in the "More actions" sheet (print, export, memory vault, caregivers, language, settings).
- All modals are bottom sheets under 640 px.

---

## Section 6: `data-testid` & Test Suite Migration Notes

### 6.1 Preserved `data-testid`s

| testid | Location |
|---|---|
| `sidebar-wrapper` | `ChatApp` — still toggles `translate-x-0` / `-translate-x-full`. |
| `sidebar-backdrop` | `ChatApp` — rendered only below 1024 px while the drawer is open (was below 768 px). |
| `upload-progress-banner` | Now the root of `UploadStepper` (`role="status"`). Contains the text "Processing report..." while polling. |
| `metrics-skeleton` | `InspectorPanel` loading state (`role="status"`, `aria-label="Loading lab metrics"`). |

### 6.2 New `data-testid`s (for Playwright)

`workbench-header`, `conversation-pane`, `inspector-pane`, `inspector-resize-handle`, `inspector-tabs`, `mobile-view-switcher`, `mobile-insights-view`, `nav-rail`, `command-palette`, `patient-switcher-trigger`, `memory-vault`, `metric-row`, `biomarker-card`, `range-bar`, `trend-chart`, `organ-system-card`, `auth-brand-panel`.

### 6.3 Preserved accessible names (do not rename)

`Toggle sidebar` (exactly one, in the header), `Chat options`, `Rename` / `Delete` menu items, `Rename chat` textbox, `Confirm rename` / `Cancel rename`, `Log out` (sidebar footer only), `Upload report`, `Send message`, `Stop generation`, `Voice input` / `Stop listening`, `Detach {filename}`, `Export Summary` (header, desktop, report open), `Export chat data`, `View extracted lab metrics table` (desktop header button / mobile segment), `Switch to chat view` (mobile segment), `Select patient context`, `Search lab tests`, `Clear search`, `Copy response` / `Read response aloud` (titles), `Mark as helpful`, `Mark as not helpful`, `Share response`, `Regenerate response`, `Close settings`, `Close profile modal`, `Scroll to latest message`, `Dismiss upload error`. Button text `Try with a Sample Blood Test Report`, `New Conversation`, `Retry`. The sr-only text `MediSkye AI Medical Assistant` stays in the empty state.

New names: `Collapse sidebar`, `Expand sidebar`, `Start a new chat` (rail), `Upload a lab report` (rail), `Open command palette`, `Open memory vault`, `Open caregiver hub`, `Open settings`, `More actions`, `Close clinical inspector`, `Re-run biomarker extraction`, `Resize inspector panel` (`role="separator"`), `Ask MediSkye about {biomarker}`, `View clinical insights and trends`, `Dismiss upload status`, `Search chat history`, `Search remembered facts`, `Memory vault consent` (switch), `Forget: {fact}`.

### 6.4 Behavior changes tests should know about

1. **Single rendering of chat tables.** Markdown tables render once (sticky-first-column scroll card); the old duplicate mobile card list for ≥5-column tables is gone, so `getByText` on table content no longer needs `getAllByText`.
2. **Inspector default:** closed on viewports < 1280 px unless `mediskye_inspector_open=true`. JSDOM's default `innerWidth` is 1024, so existing ChatApp tests run with the inspector closed. To test the split view, set `localStorage.setItem('mediskye_inspector_open','true')` and `window.innerWidth = 1440` before render.
3. **`fetchLabMetrics` is lazy:** it is called only when the inspector / analytics view / palette is open. Mocked API modules that omit it are safe (calls are wrapped in try/catch).
4. **Sidebar default** is closed below 1024 px (the existing "<768 px closed" test still passes).
5. **The active report title is not repeated** as a standalone text node anywhere outside the sidebar (header shows the filename), so `findByText('{title}')` stays unique.
6. **ConfirmModal** now uses `z-[80]` and is a bottom sheet under 640 px; `role="dialog"` and button names are unchanged.
7. **Status pill glyphs:** `↑ High`, `↓ Low`, `✓ Normal`, `↘ {delta_alert}` unchanged; new `▲ Critical` and `~ Borderline`.
8. **RangeBar** uses `role="img"`, never `role="progressbar"` (the e2e assertion that no progressbar exists in LabMetrics still holds).

### 6.5 Test files

- Modified: `src/test/SidebarRename.test.jsx` (one class-name assertion, see §1.2).
- Added: `src/test/clinical.test.js`, `src/test/WorkbenchComponents.test.jsx`.
- Suggested Playwright additions: palette open via `Control+K` → `[data-testid=command-palette]`; inspector resize via drag on `[data-testid=inspector-resize-handle]`; mobile (Pixel 7 profile) → `[data-testid=mobile-view-switcher]` then assert the composer textbox is hidden on Lab Metrics; upload stepper text progression on `[data-testid=upload-progress-banner]`.
