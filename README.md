<div align="center">

# 🩺 MediSkye AI
### Production-Grade Clinical AI Assistant & Medical Lab Report Analyzer

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-5+-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Vertex AI](https://img.shields.io/badge/Google_Vertex_AI-Gemini_3.8_Flash-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/vertex-ai)
[![PostgreSQL](https://img.shields.io/badge/Neon_PostgreSQL-Serverless-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Firebase](https://img.shields.io/badge/Firebase_Auth-Verified-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://firebase.google.com/)
[![Cloud Run](https://img.shields.io/badge/Google_Cloud_Run-asia--southeast1-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/run)
[![Cloudflare Pages](https://img.shields.io/badge/Cloudflare_Pages-Edge-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://pages.cloudflare.com/)

**MediSkye** is a full-stack clinical intelligence platform that transforms complex medical PDFs and laboratory reports into clear, structured biomarker tables, printable physician-ready summaries, longitudinal trend charts, and interactive, grounded conversations—powered by a hybrid **FAISS + BM25 RAG pipeline** and **Google Cloud Vertex AI / Gemini API**.

[Live Demo](https://mediskye.pages.dev) • [Architecture](#-system-architecture--regional-topology) • [How Upload & Query Modes Work](#-how-every-upload--interaction-mode-works) • [Directory Map](#-repository-directory-map) • [Benchmarks](#-production-latency-benchmarks)

</div>

---

## ✨ Key Engineering Highlights

* **🧪 Clinical Obsidian Workbench Architecture:** Responsive split-pane clinical workspace featuring the `InspectorPanel` biomarker drawer, interactive SVG `RangeBar` references, `DeltaIndicator` longitudinal deltas, `TrendsView` and `TrendChart` multi-visit tracking, `CommandPalette` (Cmd+K) keyboard navigation, and physician-ready `PrintableSummary` export.
* **🛡️ Patient Profile Scoping & Dependent Isolation:** Strict `dependent_id` validation and physical query scoping across chats, documents, and memory facts (`e1a2b3c4d5e6_add_dependent_id_to_chats`), preventing cross-dependent data contamination.
* **🔬 Deterministic Biomarker Canonical Matching & Disambiguation:** Order-dependent whole-word regex matching via `canonical_biomarker_key` eliminates substring collisions (e.g. `Hemoglobin` never collides with `HbA1c`, `fasting` never collides with `AST`, and hemoglobin electrophoresis bands are disambiguated as `hb_electrophoresis`), backed by multi-tier borderline bands and age/sex strata clinical consensus.
* **⚡ Two-Phase Asynchronous Upload Pipeline:** Decouples critical-path vector indexing (**Step A: ~1.4–2.4s**) from background LLM pre-warming and cloud storage syncing (**Step B**), unblocking the user interface immediately with `index_status = "local_ready"` while warming metrics and summary caches behind the scenes.
* **🔍 Hybrid RAG Retrieval with Table Header Propagation:** Combines dense semantic vector embeddings (`models/gemini-embedding-2` batched in slices of 100) with lexical BM25 keyword scoring via Reciprocal Rank Fusion (`RRF`, $k=60$) so exact clinical acronyms (`HbA1c`, `TSH`, `eGFR`, `hs-CRP`) are never missed. Multi-page medical reports automatically propagate Markdown table headers across page breaks (`_propagate_table_headers`), ensuring continuation rows retain their column semantics.
* **📈 Longitudinal Multi-Report Tracking & Comparison:** Dedicated `GET /users/me/metrics/trends` endpoint delivers multi-visit chronologically ordered biomarker trajectories. During conversations, `<prior_lab_reports_history>` injects prior reports' `cached_metrics` directly from the database alongside semantic memory chunks, enabling full-panel longitudinal comparisons with exact source PDF attribution (`(From prior report: "filename.pdf" / YYYY-MM-DD)`).
* **🧠 0ms Deterministic Intent Router & Safety Triage:** Fast-path routing intercepts `EMERGENCY` red-flag symptoms, `CASUAL` greetings, and document-bound `DOCUMENT_QA` queries in **0ms** without burning an extra LLM classification round-trip, backed by negation-aware multilingual emergency triage (English, Hindi, Spanish, French, German, Chinese).
* **🗄️ 3-Tier Index & Database Caching:**
  * **Vector Index Tier:** In-Memory LRU Cache (`maxsize=10`) $\rightarrow$ Local Ephemeral `/tmp` Disk $\rightarrow$ Google Cloud Storage (`GCS`) fallback with `425/503 Retry-After` multi-instance protection.
  * **Clinical Artifact Tier:** Extracted biomarkers (`cached_metrics`) and printable clinical reports (`cached_summary`) are pre-warmed asynchronously upon upload and persisted in **PostgreSQL**; cached artifact responses return in sub-second latency without repeating LLM inference.
* **🔐 HIPAA-Aligned Security & Zero-PHI Auth Hot-Path Optimization:**
  * Dual **Firebase Authentication** (Google OAuth 2.0 + Email/Password with verification enforcement) + fallback local JWT support gated behind explicit development flags.
  * **Single-Flight Request Coalescing (`_single_flight`):** Parallel SPA requests at login coalesce concurrent token verification, resolving credentials once and serving subsequent requests from cache.
  * **Sub-5ms Revocation & In-Memory Digest Cache:** Immediate token revocation upon logout or password reset via in-memory SHA-256 digest cache, Redis blocklist, and database `token_invalid_before` cutoff.
  * **Fernet Symmetric Column Encryption at Rest (18 Columns):** Across 18 database columns (patient demographics, conditions, medications, allergies, blood type, occupation, dependent profiles, extracted patient facts, and chat histories), sensitive PHI is encrypted with Fernet (`AES-128-CBC` + `HMAC-SHA256`) before database writes. Decrypted clinical PHI is scrubbed from the high-throughput 60s in-memory token cache via `UserDTO` (`get_current_user` vs. `get_current_user_full`), eliminating cache-resident plaintext PHI while preserving full clinical context for RAG generation.
  * **60s SHA-256 Token TTL Cache:** Avoids redundant database round-trips on high-frequency API endpoints, with instant programmatic eviction on profile updates, password changes, logout, or account deletion (`DELETE /users/me`).
* **🛡️ Upload Hardening, Body Limits & Stream Resilience:** Pure-ASGI byte-counting body size limits (1MB JSON, 51MB upload), magic byte and dimension verification for PNG/JPEG/PDF, self-healing 120s monotonic session locking, and terminal `[DONE]` event detection guarding against interrupted SSE streams.
* **📱 Mobile-First & Accessible UI:** Responsive drawer navigation for `375px` viewports, iOS Safari auto-zoom prevention, horizontal scroll wrappers for clinical tables, full keyboard focus trapping (`useFocusTrap`) across all modals, WCAG AA `#7b8798` ink contrast, and multi-language (`i18n`) support.

---

## 🏗️ System Architecture & Regional Topology

The Cloud Build configuration deploys backend compute to **Singapore (`asia-southeast1`)** and sets Vertex AI inference to **`global`**. The configured Neon database is in **AWS Asia Pacific (Singapore, `ap-southeast-1`)**; static assets are served from **Cloudflare's Global Edge**.

```mermaid
flowchart TB
    subgraph Client["Frontend — Cloudflare Pages (Global Edge)"]
        UI["React 18 + Vite UI<br/>(Workbench, LabMetrics, PrintableSummary, TrendsView)"]
        FB_SDK["Firebase Client SDK<br/>(Google OAuth / Email+Pass / Auto Token Refresh)"]
    end

    subgraph GCP["Backend — Google Cloud Run (asia-southeast1)"]
        MW["FastAPI Middleware<br/>(CORS max_age=3600, X-Process-Time-Ms, Rate Limiter)"]
        AUTH["Auth Guard & 60s SHA-256 Token Cache<br/>(DTO vs. Full ORM PHI Loader)"]
        ROUTER["0ms Fast-Path Intent Router<br/>(EMERGENCY | CASUAL | DOCUMENT_QA | GENERAL_HEALTH)"]
        UPLOAD["2-Phase Async Upload Engine<br/>(Step A: Local Ready | Step B: Async Warmers)"]
        LRU["3-Tier Hybrid Index Resolver<br/>(1. Memory LRU -> 2. /tmp -> 3. GCS)"]
    end

    subgraph Data["Data & Cloud Storage Layer (Singapore)"]
        NEON[("Neon Serverless PostgreSQL<br/>(aws-ap-southeast-1 Pooled)<br/>Users, Docs, Chats, Cached Metrics/Summary")]
        GCS[("Google Cloud Storage<br/>Persistent FAISS + BM25 Indexes")]
    end

    subgraph AI["AI Inference — Google Cloud Vertex AI / Gemini API"]
        EMBED["Vertex AI / Gemini Embeddings<br/>(Batched 100-chunk slices, Semaphore Concurrency)"]
        GEMINI["Gemini Flash (gemini-3.6-flash / gemini-3.8-flash)<br/>(thinking_budget=0, SSE Streaming)"]
    end

    UI -->|HTTPS / SSE Stream| MW
    FB_SDK -->|ID Token JWT| AUTH
    MW --> AUTH
    AUTH --> ROUTER
    AUTH --> UPLOAD
    UPLOAD -->|Step A: Parse & Batch Embed| EMBED
    UPLOAD -->|Step A: Prime Local Index| LRU
    UPLOAD -->|Step A: Commit Document & Status| NEON
    UPLOAD -.->|Step B: Exponential Backoff Sync| GCS
    UPLOAD -.->|Step B: Pre-Warm Metrics & Summary| GEMINI
    ROUTER -->|DOCUMENT_QA| LRU
    LRU <-->|Fallback Download| GCS
    ROUTER -->|Stream Tokens| GEMINI
    GEMINI -->|Persist Chat History| NEON
```

---

## 🔄 How Every Upload & Interaction Mode Works

MediSkye supports **six distinct operational flows**, each engineered with its own isolated data pipeline and caching strategy:

### 1. Standard PDF Lab Report Upload (Two-Phase Async Pipeline)
When a user selects or drags-and-drops a `.pdf` medical report or medical scan from their device:
1. **Client-Side Pre-Flight Validation (`ChatInput.jsx`):**
   * The backend enforces the configured upload-size limit (`MEDISKYE_MAX_UPLOAD_MB`, default `50 MB`) and page limit (`MAX_PDF_PAGES`, default `100`). Accepted extensions are `.pdf`, `.jpg`, `.jpeg`, and `.png`.
2. **Phase A — Critical Path to Unblock the User (`upload.py` — Target: 3–5s):**
   * **Text Extraction & Sanitization (`parse_ms`):** Extracts digital text pages via PyMuPDF/`pypdf`. If the file is an image or radiological scan, classifies via Gemini Vision and enhances with CLAHE. If the PDF is empty or an un-OCRed scan (`len(text) < 20`), raises a clean `422 Unprocessable Entity` with an actionable explanation.
   * **Clinical Chunking (`chunk_ms`):** Splits text using `MedicalTextSplitter` into overlapping semantic blocks while protecting Markdown table rows and bullet list runs from being severed across chunk boundaries.
   * **Batched Embeddings (`embed_ms`):** Embeddings are generated in batches of 100 chunks with bounded concurrency (`EMBED_CONCURRENCY`, default 4).
   * **Hybrid Index Construction (`faiss_build_ms`):** Builds both the dense **FAISS** vector index and lexical **BM25** index in a worker thread (`asyncio.to_thread`), writes them immediately to local index storage, and primes the **in-memory LRU cache**.
   * **Instant Unblock (`db_commit_ms`):** Creates the `Document` record in PostgreSQL with `index_status = "local_ready"` and marks the upload job `COMPLETED`. The user's UI immediately unlocks for chatting!
3. **Phase B — Decoupled Post-Completion Background Workers (`upload.py`):**
   * After the user is unblocked, decoupled background tasks execute concurrently (each opening its own isolated `AsyncSessionLocal()` database session to guarantee thread-safety):
     * **Worker 1 (GCS Sync):** Uploads the FAISS + BM25 index artifacts to Google Cloud Storage with 3 exponential-backoff retries, then updates `index_status = "synced"`.
     * **Worker 2 (Metrics Pre-Warming):** Calls Gemini (`thinking_budget=0`) to extract structured JSON biomarkers and writes them to `Document.cached_metrics`.
     * **Worker 3 (Summary Pre-Warming):** Calls Gemini (`thinking_budget=0`) to generate a structured clinical summary and writes it to `Document.cached_summary`.

---

### 2. 1-Click Sample Medical Report Onboarding (Zero-File Mobile Testing)
New users—especially on mobile devices—often don't have a PDF lab report readily accessible in their device storage:
1. On the empty workbench state (`ChatWindow.jsx`), clicking a sample panel (e.g., Lipid Panel, Comprehensive Metabolic Panel, Thyroid Function, CBC, Diabetes Panel) fetches the static `/samples/report-*.pdf` bundle directly from the app as a binary `Blob`.
2. The frontend wraps the blob into a native JavaScript `File` object in memory.
3. It pipes that `File` object directly into `handleFileUpload()`, triggering the full Phase A + Phase B pipeline in a single tap without requiring the user to download and re-upload a file.

---

### 3. Document-Grounded RAG Chat (`DOCUMENT_QA`)
When a user asks a question while a document is selected in the workbench:
1. **0ms Fast-Path Intent Routing (`intent_router.py`):**
   * First checks for `EMERGENCY` red flags and `CASUAL` greetings in `0ms`.
   * Because `document_id` is attached, it immediately routes to `DOCUMENT_QA` in **0ms**, skipping the LLM classification call.
2. **3-Tier Hybrid Index Lookup & Multi-Instance Safeguard (`retriever.py` & `query.py`):**
   * Checks **Tier 1 (In-Memory LRU Cache)** $\rightarrow$ **Tier 2 (Local Storage Disk)** $\rightarrow$ **Tier 3 (Google Cloud Storage)**.
   * **Multi-Instance Safety Gate:** If Cloud Run scales horizontally and a request hits a brand-new container while `index_status` is still `"building"` or before GCS sync completes, the handler checks index availability *before* writing any `Chat` row or calling Gemini, returning `503 Service Unavailable` with `Retry-After: 2`. The frontend `api.js` interceptor automatically waits 2s and retries transparently.
3. **Hybrid Retrieval, Longitudinal Memory & Prompt Sanitization (`prompt_builder.py`):**
   * Retrieves top chunks via combined FAISS + BM25 scores, strips internal RAG metadata headers, escapes the document filename and untrusted content against prompt injection via `escape_xml_content`, and injects the user's encrypted health profile context (if consented).
   * **Longitudinal Multi-Report Comparison:** Automatically injects prior reports' `cached_metrics` under `<prior_lab_reports_history>` and formats cross-chat facts with exact source PDF attribution, instructing the model to generate clean Markdown delta tables and prevent grouping contradictory `Low` and `High` markers.
4. **Low-Latency SSE Token Streaming (`query.py`):**
   * Streams tokens from Gemini with `thinking_config=ThinkingConfig(thinking_budget=0)`, appends the clinical disclaimer upon stream completion, and saves both turns to the database for multi-device sync.

---

### 4. Standalone Health Chat, Casual Fast-Path & Emergency Interceptor
Users can also chat with MediSkye without uploading a document (`New Conversation`):
* **🚨 `EMERGENCY` Fast-Path (0ms):** Deterministic regex and multilingual matching for acute symptoms (*"chest pain"*, *"can't breathe"*, *"stroke"*, *"heart attack"*, *"severe bleeding"*, *"suicide"*). Immediately bypasses standard generation, emits a high-priority emergency warning instructing the user to call **112 / 911**, and triggers an unmissable red emergency banner in the UI.
* **👋 `CASUAL` Fast-Path (0ms):** Deterministic matching for greetings and pleasantries (*"hi"*, *"hello"*, *"hey mediskye"*, *"thanks"*, *"bye"*). Skips vector retrieval and **suppresses the medical disclaimer** so conversational greetings feel natural and human.
* **🩺 `GENERAL_HEALTH` Mode:** Answers general medical and wellness questions using Gemini with clinical safety guardrails and automatic medical disclaimers, persisting the thread in the database.

---

### 5. Automated Lab Metrics Extraction & Longitudinal Trends
* **Clinical Triage Table (`LabMetrics.jsx`):**
  * **Cache-First Serving (`metrics.py`):** Checks `doc.cached_metrics`. Because Phase B pre-warms `cached_metrics` after upload, cached requests are served in milliseconds without repeating extraction. Supports `?force_refresh=true` if re-extraction is requested.
  * **Abnormal-First Clinical Sorting:** Automatically sorts abnormal rows (**`High`** and **`Low`**) to the top of the table in red/amber text, followed by **`Normal`** biomarkers in emerald green.
* **Longitudinal Trends Endpoint (`GET /users/me/metrics/trends`):**
  * Aggregates biomarkers across all historical reports for the authenticated user or selected dependent, sorting by specimen collection date (`collected_at`) or upload date.
  * Outputs time-series data consumed by `TrendsView` and `TrendChart` to plot longitudinal biomarker trajectories.

---

### 6. Printable Multi-Page Clinical Summary Export (`PrintableSummary.jsx`)
Clicking **"Export Summary"** generates a formal, physician-ready document suitable for printing or saving as PDF:
* **Dedicated Cached Endpoint (`POST /users/me/documents/{document_id}/summary`):** Returns the document-scoped summary or generates it on demand via `build_document_summary_prompt` if it has not yet been cached.
* **Print-Optimized Layout:** Strips emojis, renders clean clinical Markdown sections (*Executive Overview*, *Abnormal Findings by Organ System*, *Recommended Follow-Up Questions for Your Physician*), populates `<PrintableSummary/>`, and triggers `window.print()` with `@media print` CSS rules that hide the app sidebar and format clean page breaks.

---

## 📂 Complete Repository Directory Map

Project directory overview based on the current local workspace:

```text
MediSkye/
├── .github/
│   └── workflows/tests.yml     # GitHub Actions CI test workflow
├── backend/
│   ├── alembic/
│   │   ├── versions/           # Database migration versions
│   │   ├── env.py
│   │   ├── README
│   │   └── script.py.mako
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.py     # Auth, registration, login, logout, verification
│   │   │   │   ├── chat.py     # Chat document associations
│   │   │   │   ├── health.py   # Health, liveness, and readiness probes
│   │   │   │   ├── metrics.py  # Lab metrics extraction & longitudinal trends
│   │   │   │   ├── query.py    # RAG query streaming, chat rename, doc summary
│   │   │   │   ├── upload.py   # Async file upload, status, cache pre-warming
│   │   │   │   └── user.py     # User profiles, dependents, chats, facts, memory
│   │   │   └── router.py       # API router aggregating v1 endpoints
│   │   ├── core/
│   │   │   ├── audit.py        # Audit logging service
│   │   │   ├── auth.py         # JWT tokens, password hashing, DTO, token cache
│   │   │   ├── config.py       # Pydantic BaseSettings configuration
│   │   │   ├── limiter.py      # SlowAPI rate limiter
│   │   │   ├── logging.py      # Structured JSON / console logger
│   │   │   ├── observability.py# Sentry error tracking with PHI scrubbing
│   │   │   ├── redis_client.py # TTL-aware bounded MockRedis
│   │   │   └── security.py     # Text/filename sanitization, API key guard
│   │   ├── db/
│   │   │   ├── database.py     # SQLAlchemy async engine, sessionmaker, Base
│   │   │   ├── encryption.py   # Fernet EncryptedString, EncryptedText, EncryptedJSON
│   │   │   └── models.py       # User, Dependent, Document, Chat, PatientFact, etc.
│   │   ├── llm/
│   │   │   ├── embeddings_client.py # Gemini embeddings client with retry
│   │   │   └── gemini_client.py     # Gemini generative client with fallback models
│   │   ├── middleware/
│   │   │   ├── body_limit.py        # Body size limit middleware (1MB JSON, 51MB upload)
│   │   │   ├── error_handler.py     # Global exception handlers
│   │   │   ├── request_id.py        # X-Request-ID propagation middleware
│   │   │   └── security_headers.py  # Security response headers middleware
│   │   ├── rag/
│   │   │   ├── prompts/
│   │   │   │   └── fact_extraction.txt # Prompt template for fact extraction
│   │   │   ├── chunking.py          # MedicalTextSplitter with table/bullet atomization
│   │   │   ├── embedder.py          # ResilientGeminiEmbeddings wrapper
│   │   │   ├── hybrid_search.py     # BM25Index and Reciprocal Rank Fusion (RRF)
│   │   │   ├── index_storage.py     # Local / GCS index artifact persistence
│   │   │   ├── intent_router.py     # Agentic Intent Router (0ms fast path + LLM)
│   │   │   ├── loader.py            # PDF / image extractor with Vision & CLAHE
│   │   │   ├── output_filter.py     # Output scanner for injection markers
│   │   │   ├── prompt_builder.py    # Clinical RAG prompt construction
│   │   │   ├── retriever.py         # FAISS + BM25 hybrid retriever & cross-doc search
│   │   │   └── safety.py            # Emergency detection & multilingual crisis triage
│   │   ├── schemas/
│   │   │   ├── dependent.py         # DependentProfile schemas
│   │   │   ├── health.py            # HealthCheckResponse schema
│   │   │   ├── query.py             # QueryRequest schema
│   │   │   ├── upload.py            # UploadJobResponse, LabMetricItem, MetricsResponse
│   │   │   └── user.py              # UserCreate, UserUpdate, UserResponse, PatientFact
│   │   ├── services/
│   │   │   ├── chat_indexer.py      # Semantic chat chunk indexer
│   │   │   ├── clinical_units.py    # Clinical units, ranges, and chronology parser
│   │   │   ├── email_service.py     # Gmail SMTP transactional email dispatcher
│   │   │   ├── fact_extractor.py    # Gemini-powered clinical fact extraction
│   │   │   ├── fact_persistence.py  # PatientFact persistence & deduplication
│   │   │   ├── memory_formatter.py  # Long-term memory prompt formatting
│   │   │   ├── patient_memory.py    # Patient memory querying & retrieval
│   │   │   ├── patient_service.py   # Patient age & profile calculation
│   │   │   ├── pdf_service.py       # File upload validation (PDF/image magic bytes)
│   │   │   ├── phi_backfill.py      # PHI encryption verification & backfill helpers
│   │   │   └── upload_jobs.py       # Asynchronous upload job lifecycle manager
│   │   └── main.py                  # FastAPI application entry point
│   ├── scripts/
│   │   ├── api_benchmark.py         # Direct Cloud Run API latency benchmark (N=10)
│   │   ├── backfill_encrypt_phi.py  # CLI script for PHI encryption backfill
│   │   └── latency_profiler.py      # Playwright E2E browser latency profiler (N=5)
│   ├── tests/
│   │   ├── eval/                    # Prompt quality evaluation tests
│   │   ├── fixtures/test_report.pdf # Sample report fixture
│   │   ├── conftest.py              # Pytest configuration and fixtures
│   │   └── test_*.py                # 73 backend test suites (508 passed tests)
│   ├── .dockerignore
│   ├── .env.example
│   ├── Dockerfile                   # Cloud Run container definition
│   ├── alembic.ini
│   ├── docker-compose.yml
│   ├── main.py                      # Root backwards-compatibility entry point
│   ├── pyproject.toml
│   ├── requirements-dev.txt
│   ├── requirements.txt
│   └── start.sh
├── frontend/
│   ├── public/
│   │   └── samples/                 # Sample clinical PDF reports for demo
│   ├── src/
│   │   ├── components/
│   │   │   ├── auth/
│   │   │   │   └── AuthShell.jsx    # Responsive authentication wrapper
│   │   │   ├── clinical/
│   │   │   │   ├── DeltaIndicator.jsx       # Longitudinal delta display
│   │   │   │   ├── OrganSystemsOverview.jsx # Organ system triage cards
│   │   │   │   ├── RangeBar.jsx             # SVG biomarker reference range bar
│   │   │   │   ├── StatusPill.jsx           # Clinical status pill indicator
│   │   │   │   ├── TrendChart.jsx           # Interactive biomarker trend chart
│   │   │   │   └── TrendsView.jsx           # Multi-visit biomarker trends table
│   │   │   ├── landing/
│   │   │   │   ├── CTASection.jsx
│   │   │   │   ├── FeaturesSection.jsx
│   │   │   │   ├── FooterSection.jsx
│   │   │   │   ├── HowItWorksSection.jsx
│   │   │   │   ├── SafetySection.jsx
│   │   │   │   └── shared.jsx
│   │   │   ├── ui/
│   │   │   │   ├── IconButton.jsx
│   │   │   │   ├── Kbd.jsx
│   │   │   │   ├── SegmentedControl.jsx
│   │   │   │   └── Sheet.jsx
│   │   │   ├── workbench/
│   │   │   │   ├── Brand.jsx            # Brand mark & typography
│   │   │   │   ├── CommandPalette.jsx   # Cmd+K quick actions palette
│   │   │   │   ├── InspectorPanel.jsx   # Clinical inspector drawer
│   │   │   │   ├── MemoryVault.jsx      # Memory facts manager
│   │   │   │   ├── NavRail.jsx          # Collapsible navigation rail
│   │   │   │   ├── PatientSwitcher.jsx  # Multi-dependent patient selector
│   │   │   │   ├── UploadStepper.jsx    # Two-phase upload progress stepper
│   │   │   │   └── Workbench.jsx        # Clinical Obsidian Workbench layout
│   │   │   ├── AuthAction.jsx           # Firebase action link handler
│   │   │   ├── ChatApp.jsx              # Main chat application coordinator
│   │   │   ├── ChatInput.jsx            # Message composer with file attachment
│   │   │   ├── ChatMessage.jsx          # Message bubble with markdown & sources
│   │   │   ├── ChatWindow.jsx           # Chat message list & empty states
│   │   │   ├── ConfirmModal.jsx         # Action confirmation dialog
│   │   │   ├── DocumentModal.jsx        # Document details modal
│   │   │   ├── ExportModal.jsx          # Conversation & report export dialog
│   │   │   ├── LabMetrics.jsx           # Biomarker table with range visualization
│   │   │   ├── LandingPage.jsx          # Marketing landing page
│   │   │   ├── Login.jsx                # Firebase sign-in with Google / Email
│   │   │   ├── MemoryConsentModal.jsx   # Long-term memory opt-in modal
│   │   │   ├── PrintableSummary.jsx     # Physician-ready A4 clinical summary
│   │   │   ├── PrintableTranscript.jsx  # Printable conversation transcript
│   │   │   ├── PrivacyPolicy.jsx        # Privacy policy page
│   │   │   ├── Profile.jsx              # User account & dependents modal
│   │   │   ├── Register.jsx             # Account registration page
│   │   │   ├── SettingsModal.jsx        # Application preferences modal
│   │   │   └── Sidebar.jsx              # Chat history & document navigation sidebar
│   │   ├── hooks/
│   │   │   ├── useFocusTrap.js          # Focus trap for accessible dialogs
│   │   │   ├── useHotkeys.js            # Keyboard shortcuts hook
│   │   │   ├── useIntersectionObserver.js # Lazy viewport observer
│   │   │   ├── useLabMetrics.js         # Lab metrics querying & caching hook
│   │   │   ├── useResizablePane.js      # Resizable inspector pane hook
│   │   │   ├── useTrendData.js          # Longitudinal trend data loader
│   │   │   └── useViewport.js           # Responsive viewport breakpoint hook
│   │   ├── lib/
│   │   │   ├── clinical.js              # Biomarker normalization & delta calculations
│   │   │   ├── cn.js                    # Tailwind class merger utility
│   │   │   └── storageKeys.js           # Centralized LocalStorage keys
│   │   ├── locales/                     # i18next translation catalogs (en, hi)
│   │   ├── services/
│   │   │   ├── api.js                   # Backend API client with streaming SSE
│   │   │   ├── firebase.js              # Firebase Client SDK initialization
│   │   │   ├── logger.js                # Frontend client logger
│   │   │   ├── speech.js                # Web Speech API text-to-speech
│   │   │   └── storage.js               # Local storage helper
│   │   ├── styles/print.css             # Print media stylesheet
│   │   ├── test/                        # Vitest test suite (26 files, 208 tests)
│   │   ├── App.jsx                      # Root router & protected route guard
│   │   ├── i18n.js                      # Internationalization configuration
│   │   ├── index.css                    # Tailwind CSS entry point
│   │   ├── instrument.js                # Sentry frontend instrumentation
│   │   └── main.jsx                     # Vite DOM entry point
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── vitest.config.js
├── .gitignore
├── Makefile
├── README.md                            # Comprehensive project documentation
└── cloudbuild.yaml                      # Google Cloud Build deployment pipeline
```

---

## 📊 Production Latency Benchmarks

Latest production benchmark snapshot (Direct Cloud Run API across N=10 warm runs & browser E2E Playwright across N=5 runs on Singapore regional cluster `asia-southeast1`):

### Direct Cloud Run API (Table A, N=10 warm runs)

| Endpoint | Cold (1st Hit) | Warm p50 (N=10) | Warm p95 (N=10) | Server X-Process-Time (p50 / p95) | Successful warm requests | n_425 | n_429 | n_retries |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `GET /health` | 267.9 ms | 148.5 ms | 213.6 ms | 0.5 / 0.9 ms | 10/10 | 0 | 0 | 0 |
| `GET /users/me` (Auth Cache Hit) | 149.9 ms | 203.7 ms | 5,940.7 ms | 29.7 / 34.2 ms | 10/10 | 0 | 0 | 0 |
| `GET /users/me/documents/{id}/metrics (cached hit)` | 250.9 ms | 252.9 ms | 360.8 ms | 39.1 / 49.0 ms | 10/10 | 0 | 0 | 0 |
| `POST /users/me/documents/{id}/summary (cached hit)` | 165.5 ms | 199.9 ms | 244.1 ms | 29.2 / 34.3 ms | 10/10 | 0 | 0 | 0 |
| `POST /query (GENERAL_HEALTH)` | 1,178.0 ms | 1,473.7 ms | 1,638.0 ms | 1,136.5 / 1,480.9 ms | 10/10 | 0 | 0 | 0 |
| `POST /query (DOCUMENT_QA)` | 341.4 ms | 375.1 ms | 946.0 ms | 205.4 / 808.8 ms | 10/10 | 0 | 0 | 0 |
| `POST /query (IDOR 404 Rejection)` | 184.1 ms | 236.1 ms | 250.1 ms | 48.8 / 67.0 ms | 10/10 | 0 | 0 | 0 |

*Note: For `GET /users/me`, server processing time remained tightly bounded at 29.7 ms (p50) and 34.2 ms (p95); elevated client p95 reflects Cloud Run HTTP/2 ALPN renegotiation and trans-oceanic edge routing jitter on two cold connections.*

| Upload / Cold-Start Measurement | Observed Latency | Server Processing Time |
| :--- | ---: | ---: |
| First Hit (Cloud Run Idle/Wakeup `GET /health`) | 608.2 ms | 0.4 ms |
| Observed Upload Synchronous Fast-Path Total (`local_ready`) | 6,167.5 ms | — |

### Browser E2E Benchmark (Table B, Playwright, DOCUMENT_QA Workload, N=5 runs)

| Metric / Step | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 | Warm p50 (N=5) | Warm p95 (N=5) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Page Load | 1,764.4 ms | 1,777.6 ms | 1,766.3 ms | 2,275.7 ms | 1,910.3 ms | **1,777.6 ms** | **2,202.6 ms** |
| Login & Auth Redirect | 3,275.2 ms | 2,914.5 ms | 3,304.2 ms | 2,851.7 ms | 12,049.6 ms | **3,275.2 ms** | **10,300.5 ms** |
| PDF Upload & Processing | 1,454.5 ms | 1,444.3 ms | 1,427.8 ms | 1,906.5 ms | 5,998.4 ms | **1,454.5 ms** | **5,180.0 ms** |
| Lab Metrics (1st Run) | 111.9 ms | 110.3 ms | 106.9 ms | 103.2 ms | 176.3 ms | **110.3 ms** | **163.4 ms** |
| Lab Metrics (Cached) | 120.0 ms | 161.0 ms | 102.3 ms | 133.2 ms | 175.7 ms | **133.2 ms** | **172.8 ms** |
| Print Summary (1st Run) | 1,627.9 ms | 951.6 ms | 827.3 ms | 837.9 ms | 770.3 ms | **837.9 ms** | **1,492.6 ms** |
| Print Summary (Cached) | 408.4 ms | 363.6 ms | 388.1 ms | 368.7 ms | 363.4 ms | **368.7 ms** | **404.3 ms** |
| AI Chat TTFT (1st Token) | 2,010.7 ms | 2,178.8 ms | 2,387.0 ms | 2,512.7 ms | 2,621.5 ms | **2,387.0 ms** | **2,599.7 ms** |
| AI Chat Total Stream | 16,137.7 ms | 13,993.7 ms | 12,998.9 ms | 15,266.2 ms | 12,459.6 ms | **13,993.7 ms** | **15,963.4 ms** |

### Per-Stage Upload Breakdown (Table C, UPLOAD_BREAKDOWN)

| Pipeline Stage | Observed Duration (ms) | Percentage of Total | Notes / Safeguards |
| :--- | ---: | ---: | :--- |
| `parse` | 42 ms | 1.75% | PyMuPDF text stream extraction |
| `chunk` | 18 ms | 0.75% | `MedicalTextSplitter` with table header propagation |
| `embed` | 2,120 ms | 88.33% | Vertex AI batched in slices of 100 (`EMBED_CONCURRENCY=4`) |
| `faiss_build` | 134 ms | 5.58% | In-memory FAISS & BM25 generation |
| `db_commit` | 86 ms | 3.58% | `index_status = 'local_ready'`, job flipped to `COMPLETED` |
| `background_gcs_sync` | 1,480 ms | Background (Offloaded) | Async GCS sync with exponential retry backoff (3 attempts) |
| **Total Synchronous Upload** | **2,400 ms** | **100.00%** | **Instant Ready Contract (Flipped before background tasks)** |

*Note: Table C reflects single-document backend instrumentation profiling (2,400 ms synchronous processing time), distinct from Table B's end-to-end browser Playwright measurements.*

### In-Process Subsystem Micro-Benchmarks (N=50 iterations)

| Subsystem Component | Scope & Workload | 50-Run Total | Mean per Operation |
| :--- | :--- | ---: | ---: |
| **Fernet PHI Roundtrip** | Symmetric AES-128-CBC + HMAC-SHA256 encryption & decryption of demographic & medical note payload | 6.44 ms | **0.1289 ms / op** |
| **6-Language Emergency Regex** | Triage detection across English, Spanish, French, German, Hindi, and Chinese acute symptom phrases | 34.22 ms | **0.0978 ms / op** |
| **Clinical Parser & Demographic Range Engine** | `_resolve_status` & `canonical_biomarker_key` resolution across Hemoglobin, HbA1c, Fasting Glucose, TSH, Creatinine | 20.40 ms | **0.0816 ms / op** |
| **Table Splitter & Output Filter** | `_propagate_table_headers` across page boundaries + `split_medical_documents` + `strip_emojis` + `append_disclaimer` | 8.71 ms | **0.1742 ms / op** |

### Security & Error-Code Verification Gate

| Security / Resilience Gate | Observed Response | Status |
| :--- | :--- | :---: |
| **401 Unauthorized** (Missing & Tampered Bearer Token) | `401 / 401` | **PASS** |
| **403 Forbidden** (Unverified Email Token Rejected) | `403 (Email not verified)` | **PASS** |
| **429 Too Many Requests** (Rate Limit Threshold Gate) | `429 (Per-instance SlowAPI in-memory store)` | **PASS** |
| **POST /logout Invalidation Latency** | `206.0 ms` (Server: 47.16 ms, Code 200) | **PASS** |
| **Immediate Post-Logout GET /users/me 401 Rejection** | `203.6 ms` (Server: 0.87 ms, Code 401) | **PASS** |
| **Physical Hard-Delete Cleanup Gate** | 0 benchmark test users remaining in Neon PostgreSQL | **PASS** |

---

## 🛡️ Security, Privacy & SRE Hardening

1. **Zero Unverified Access (`403 Forbidden`):** Email/Password accounts must verify their email address before accessing protected workspace resources. Google OAuth accounts with verified emails pass seamlessly.
2. **Strict Cross-User Isolation (Zero IDOR):** Every document, metric, summary, dependent, and chat history query filters strictly by `user_id == current_user.id`.
3. **Fernet PHI & Chat Encryption at Rest:** Patient health profiles (`conditions`, `medications`, `allergies`, `blood_type`, `occupation`), dependent profiles, extracted patient memory facts (`patient_facts.fact_text`), and chat message histories (`chats.message`) are encrypted using Fernet (`AES-128-CBC` + `HMAC-SHA256`) before touching PostgreSQL, with transparent ORM decryption and graceful legacy plaintext compatibility.
4. **Physical Cascade Hard-Delete for Patient Memory:** Deleting a chat session (`DELETE /users/me/chats/sessions/{session_id}`), clearing chats (`DELETE /users/me/chats`), deleting a document (`DELETE /users/me/documents/{document_id}`), deleting a dependent, or clearing facts (`DELETE /users/me/memory/facts`) performs an immediate physical cascade hard-delete in PostgreSQL (guaranteeing physical erasure rather than soft-delete retention).
5. **Prompt Injection Defense:** Uploaded filenames, text excerpts, and document chunks are sanitized against XML/HTML tag breakout (`<document name="...">`) before prompt assembly via `escape_xml_content` and `sanitize_text`.
6. **Mid-Stream Disconnect Safety:** The SSE generator in `query.py` catches `(asyncio.CancelledError, GeneratorExit)` to cleanly roll back or close database sessions if a user closes their browser tab mid-stream, preventing database connection pool leaks and eliminating orphaned turns.

---

## 🚀 Local Development Setup

### Prerequisites
* **Python 3.11+**
* **Node.js 20+** & **npm**
* **PostgreSQL** (Local instance or free **Neon Serverless PostgreSQL** project) or local SQLite for testing
* **Google Cloud Project** with **Gemini API** key or **Vertex AI API** enabled (`gcloud auth application-default login`)
* **Firebase Project** with **Authentication** (Email/Password & Google Sign-In) enabled

### 1. Clone the Repository
```bash
git clone https://github.com/AdityaSharma2k04/mediskye.git
cd mediskye
```

### 2. Backend Setup (`backend/`)
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
```

Create `backend/.env` from `backend/.env.example` and populate values:
```env
DATABASE_URL=sqlite+aiosqlite:///./mediskye.db
REDIS_URL=redis://localhost:6379/0
ENV=development
DEBUG=true
GOOGLE_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.6-flash
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_ENTERPRISE=false
GCS_INDEX_BUCKET=
JWT_SECRET_KEY=replace-with-at-least-32-random-characters
FERNET_KEY=replace-with-a-generated-fernet-key
MEDISKYE_API_KEY=
SMTP_USER=
SMTP_PASSWORD=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
MEDISKYE_MAX_UPLOAD_MB=50
MAX_PDF_PAGES=100
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_RELEASE=
```

Generate local encryption and signing keys:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Run database migrations and start the FastAPI server:
```bash
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup (`frontend/`)
```bash
cd ../frontend
npm ci
```

Create `frontend/.env` with your Firebase Web app configuration:
```env
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=your-firebase-web-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-firebase-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-firebase-app-id
VITE_SENTRY_DSN=
VITE_SENTRY_ENVIRONMENT=development
VITE_SENTRY_RELEASE=
```

Start the Vite development server:
```bash
npm run dev
```

---

## 🧪 Running the Test & Benchmark Suites

The automated test suites pass **501 backend pytest tests** and **207 frontend Vitest tests across 26 test files** (**708 total passed tests** with 0 failures).

### 1. Backend Test Suite (`pytest`)
```bash
cd backend
pytest tests -v -m "not integration" --durations=15
```
*Current status: 501 passed in 63.83s (top duration: 4.79s).*

### 2. Frontend Test Suite & Production Build (`Vitest` + `Vite`)
```bash
cd frontend
npm test -- --run
npm run build
```
*Current status: 26 test files passed (207 tests) in 53.06s; production build completed in 17.84s (0 bundle size warnings).*

---

## 🔗 Verified API Paths

The API router is mounted with `API_V1_STR` (default empty string in `backend/app/core/config.py`). Current backend paths have no `/api/v1` prefix unless explicitly configured:

| Capability | Implemented path(s) |
| :--- | :--- |
| **Health** | `GET /health`, `GET /liveness`, `GET /readiness` |
| **Authentication** | `POST /register`, `POST /login`, `POST /logout`<br/>`POST /auth/send-custom-verification`, `POST /send-custom-verification`<br/>`POST /auth/send-custom-password-reset`, `POST /send-custom-password-reset` |
| **Upload and Status** | `POST /upload`, `GET /upload/status/{job_id}` |
| **RAG Query** | `POST /query` (Streaming SSE or JSON)<br/>`PATCH /documents/{document_id}/title` |
| **Documents** | `GET /users/me/documents`<br/>`PATCH /users/me/documents/{document_id}/title`<br/>`GET /users/me/documents/{document_id}/export`<br/>`DELETE /users/me/documents/{document_id}` |
| **Chat Sessions & History** | `GET /users/me/chats`<br/>`GET /users/me/documents/{document_id}/chats`<br/>`PATCH /users/me/chats/sessions/{session_id}`<br/>`DELETE /users/me/chats/sessions/{session_id}`<br/>`DELETE /users/me/chats`<br/>`DELETE /users/me/chats/{chat_id}`, `DELETE /chats/{chat_id}`<br/>`GET /chats/{chat_id}/documents`<br/>`POST /chats/{chat_id}/documents/{doc_id}`<br/>`DELETE /chats/{chat_id}/documents/{doc_id}` |
| **Patient Memory & Facts** | `POST /users/me/memory/consent`, `POST /memory/consent`, `PATCH /users/me/memory-consent`<br/>`GET /users/me/memory/status`, `GET /memory/status`<br/>`GET /users/me/facts`, `GET /users/me/memory/facts`, `GET /memory/facts`<br/>`POST /users/me/facts`<br/>`PATCH /users/me/facts/{fact_id}`<br/>`DELETE /users/me/facts/{fact_id}`, `DELETE /users/me/memory/facts/{fact_id}`, `DELETE /memory/facts/{fact_id}`<br/>`DELETE /users/me/memory/facts`, `DELETE /memory/facts` |
| **User Profile & Account** | `GET /users/me`, `PUT /users/me`, `PATCH /users/me`<br/>`POST /users/me/password` *(deprecated)*<br/>`DELETE /users/me`<br/>`GET /users/me/export-data` |
| **Dependents** | `GET /users/me/dependents`<br/>`POST /users/me/dependents`<br/>`PUT /users/me/dependents/{dependent_id}`<br/>`DELETE /users/me/dependents/{dependent_id}` |
| **Lab Metrics & Trends** | `POST /extract-metrics`<br/>`GET /users/me/documents/{document_id}/metrics`, `POST /users/me/documents/{document_id}/metrics`<br/>`GET /users/me/metrics/trends` *(Longitudinal multi-visit trends)* |
| **Document Summary** | `GET /users/me/documents/{document_id}/summary`, `POST /users/me/documents/{document_id}/summary` |

---

## ☁️ Production Deployment

* **Backend (Google Cloud Run):** Automatically built and deployed via `cloudbuild.yaml` to `asia-southeast1` with `--session-affinity`, `--no-cpu-throttling`, `--cpu-boost`, and `2Gi` memory.
* **Frontend (Cloudflare Pages):** Automatically deployed from the `main` branch (`frontend/` directory, build command `npm run build`, output directory `dist`).
* **Database (Neon Serverless PostgreSQL):** Hosted in `AWS Asia Pacific (Singapore) — ap-southeast-1` with PgBouncer connection pooling enabled.

### Backend Environment Variables (Cloud Run)

| Variable | Secret? | Purpose / Description |
| :--- | :---: | :--- |
| `DATABASE_URL` | Yes | PostgreSQL connection URL (e.g. `postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Yes | JWT signing secret key (minimum 32 characters) |
| `FERNET_KEY` | Yes | Fernet 32-byte url-safe base64 key for column-level PHI encryption |
| `GOOGLE_API_KEY` | Yes | Gemini API key (when not using Vertex AI enterprise mode) |
| `MEDISKYE_API_KEY` | Yes | Optional API key for external webhook / API protection |
| `SMTP_USER` | Yes | Gmail address for sending transactional verification and reset emails |
| `SMTP_PASSWORD` | Yes | Gmail App Password for SMTP authentication |
| `SMTP_HOST` | No | SMTP server hostname (default: `smtp.gmail.com`) |
| `SMTP_PORT` | No | SMTP server port (default: `587`) |
| `GEMINI_MODEL` | No | Model name (e.g. `gemini-3.6-flash`, `gemini-3.8-flash`) |
| `GOOGLE_CLOUD_PROJECT` | No | Google Cloud project ID |
| `GOOGLE_CLOUD_LOCATION` | No | Google Cloud location (default: `global` or `us-central1`) |
| `GOOGLE_GENAI_USE_ENTERPRISE` | No | Set `true` to use Vertex AI with Cloud Run service identity |
| `GCS_INDEX_BUCKET` | No | Cloud Storage bucket name for persistent vector index storage |
| `REDIS_URL` | No | Redis connection URL for centralized token revocation and rate limits |
| `ALLOWED_ORIGINS` | No | Comma-separated allowed browser origins (e.g. `https://mediskye.pages.dev`) |
| `SENTRY_DSN` | Yes | Optional backend Sentry DSN |
| `SENTRY_ENVIRONMENT` | No | Sentry environment (`production`, `staging`, `development`) |
| `SENTRY_RELEASE` | No | Sentry release identifier |

### Frontend Environment Variables (Cloudflare Pages)

| Public Variable | Purpose |
| :--- | :--- |
| `VITE_API_URL` | Backend API base URL (e.g. `https://api.mediskye.pages.dev`) |
| `VITE_FIREBASE_API_KEY` | Firebase Web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase Auth domain (e.g. `your-project.firebaseapp.com`) |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Firebase Storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase Web application ID |
| `VITE_SENTRY_DSN` | Optional frontend Sentry DSN |
| `VITE_SENTRY_ENVIRONMENT` | Frontend Sentry environment |
| `VITE_SENTRY_RELEASE` | Frontend Sentry release identifier |

---

## 📱💻 Native Desktop (Windows `.exe`) & Mobile (Android `.apk`) Packaging

MediSkye is packaged natively for both desktop and mobile platforms with direct Cloud Run API integration and native origin CORS whitelisting:
- **Windows Desktop:** Built with **Tauri v2** (`.exe` NSIS installer & `.msi`), providing a lightweight (<15MB) native desktop application powered by Microsoft Edge WebView2.
- **Android Mobile:** Built with **Capacitor**, providing an Android app package (`.apk` / `.aab`) with native status bar theming, splash screen, and full gesture safe-area inset adaptation.

### Download Pre-Built Installers from GitHub Actions

Ready-to-install packages are compiled automatically by the GitHub Actions Cloud Builder on every release and main commit:
1. Navigate to the repository's **Actions** tab $\rightarrow$ **Build Native Apps** workflow.
2. Select the latest successful workflow run.
3. Under **Artifacts** at the bottom of the summary page, download:
   - **`MediSkye-Android-APK`**: Contains `app-debug.apk` (sideload directly onto any Android device).
   - **`MediSkye-Windows-Installer`**: Contains `MediSkye_1.0.0_x64-setup.exe` (NSIS installer) and `MediSkye_1.0.0_x64_en-US.msi`.

### Local Build Commands

To build native packages locally from source:

```bash
# Navigate to the frontend directory
cd frontend

# ── Android (Capacitor) ──
# Sync the built web assets to the native Android project
npm run cap:sync

# Open Android Studio to test or sign release builds
npm run cap:open

# Compile debug APK directly with Gradle
npm run android:build

# ── Windows Desktop (Tauri v2) ──
# Run Tauri in local desktop development mode (hot-reloaded)
npm run tauri:dev

# Build production Windows NSIS (.exe) and MSI (.msi) installers
npm run tauri:build
```

---

## ⚠️ Medical Disclaimer

*MediSkye is an informational clinical AI assistant designed for educational and health literacy purposes only. It is not a licensed medical professional and does not provide medical diagnoses or treatment plans. Always consult a qualified physician or healthcare provider regarding any medical condition or laboratory result. In case of a medical emergency, call 112 or 911 immediately.*
