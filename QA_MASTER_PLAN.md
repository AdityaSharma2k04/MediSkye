# 🧪 MediSkye Master QA & Persistence Testing Plan

> **Role & Authority**: Principal QA Automation Engineer  
> **Target Environment**: MediSkye Full-Stack Production & Staging Replica (FastAPI ASGI + Neon Serverless PostgreSQL + Firebase Auth + Vertex AI Gemini 3.8 Flash + Vite/React Frontend)  
> **Audience**: Autonomous QA Execution AI Agents and Automation Engineers  
> **Execution Directives**: Execute sequentially. Check off each box `[ ]` as verification passes. If any step fails, capture the response body, server stderr log, and DB state before aborting.

---

## 📋 System Under Test (SUT) Pre-Flight Configuration

Before beginning test execution, the executing agent must ensure the following environment variables and database access are verified:

- [ ] **Backend Base URL**: `http://localhost:8000` (or staging Cloud Run endpoint)
- [ ] **Frontend Base URL**: `http://localhost:5173` (or staging Cloudflare Pages endpoint)
- [ ] **Database Connection**: `DATABASE_URL` pointing to Neon PostgreSQL (`postgresql+asyncpg://...`)
- [ ] **Direct Neon SQL Client**: `psql "$DATABASE_URL"` or `asyncpg` execution harness ready
- [ ] **Current Migration State Verified**:
  ```bash
  cd backend && python -m alembic current
  # Expected output: 42c20d3c704c (head)
  ```

---

## 1. Authentication & User Lifecycle

### 1.1 Sign Up, Custom SMTP Verification & PostgreSQL Auto-Provisioning
Verifies Firebase Authentication integration, NIST SP 800-63B compliant signup, secure email verification link generation without leaking account existence, and automatic DB user record creation.

#### Test Steps
- [ ] **UI-1.1.1**: Navigate to `/register` in browser (or headless Chromium).
- [ ] **UI-1.1.2**: Enter new unique test email: `qa_user_<TIMESTAMP>@test.com` and password `MediskyeSecurePass2026!`.
- [ ] **UI-1.1.3**: Check the mandatory **PHI Consent** checkbox (`name="phi_consent"`).
- [ ] **UI-1.1.4**: Click **"Create Account"** (`button[type="submit"]`).
- [ ] **UI-1.1.5**: Verify UI displays the email verification confirmation banner: *"Check your email for a verification link"*.
- [ ] **API-1.1.6**: Attempt immediate login with unverified email via `POST /login`:
  ```bash
  curl -X POST "http://localhost:8000/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=qa_user_<TIMESTAMP>@test.com&password=MediskyeSecurePass2026!"
  ```
  - **Expected Status**: `403 Forbidden`
  - **Expected Detail**: `"Email not verified. Please check your inbox or resend verification."`
- [ ] **DB-1.1.7**: Execute database query to confirm row creation:
  ```sql
  SELECT id, email, phi_consent_granted, consent_timestamp, memory_consent_granted, created_at
  FROM users 
  WHERE email = 'qa_user_<TIMESTAMP>@test.com';
  ```
  - **Expected Verification**: Exactly **1 row** exists; `phi_consent_granted = true`; `consent_timestamp IS NOT NULL`; `memory_consent_granted = false` (default opt-out).

#### Verification Checklist
- [ ] No plaintext password exists in DB: `SELECT hashed_password FROM users WHERE email = 'qa_user_<TIMESTAMP>@test.com';` (must start with `$2b$12$` bcrypt hash or Firebase UID placeholder).
- [ ] Audit log entry logged:
  ```sql
  SELECT action_type, resource, ip_address 
  FROM audit_logs 
  WHERE user_id = (SELECT id FROM users WHERE email = 'qa_user_<TIMESTAMP>@test.com')
  ORDER BY timestamp DESC LIMIT 1;
  ```
  - **Expected**: `action_type = 'REGISTRATION'`.

---

### 1.2 Profile Update, Fernet PHI Encryption at Rest & 60s Auth Cache Eviction
Verifies that patient health profile updates encrypt PHI fields with Fernet (`AES-128-CBC` + `HMAC-SHA256`) before writing to PostgreSQL, and that the 60-second in-memory token cache immediately invalidates upon write.

#### Test Steps
- [ ] **SETUP-1.2.1**: Authenticate and obtain JWT bearer token `TOKEN_A`.
- [ ] **API-1.2.2**: Prime the 60-second auth cache by calling `GET /users/me`:
  ```bash
  curl -X GET "http://localhost:8000/users/me" -H "Authorization: Bearer $TOKEN_A"
  ```
  - **Expected Status**: `200 OK` (Cache now stores token digest -> user payload).
- [ ] **API-1.2.3**: Update profile with sensitive medical data via `PUT /users/me`:
  ```bash
  curl -X PUT "http://localhost:8000/users/me" \
    -H "Authorization: Bearer $TOKEN_A" \
    -H "Content-Type: application/json" \
    -d '{
      "full_name": "QA Principal Patient",
      "blood_type": "O-Positive",
      "known_allergies": "Penicillin, Sulfa drugs",
      "pre_existing_conditions": "Asthma, Mild Hypertension",
      "current_medications": "Albuterol inhaler, Lisinopril 10mg",
      "height_cm": 178.5,
      "diet_type": "vegetarian",
      "activity_level": "moderate"
    }'
  ```
  - **Expected Status**: `200 OK`
- [ ] **DB-1.2.4 (CRITICAL)**: Inspect raw PostgreSQL columns directly via SQL (bypassing ORM):
  ```sql
  SELECT blood_type, known_allergies, pre_existing_conditions, current_medications
  FROM users 
  WHERE email = 'qa_user_<TIMESTAMP>@test.com';
  ```
  - **Expected Verification**: Every single one of these 4 fields **MUST start with `gAAAAA`** (Fernet ciphertext). **Zero plaintext is permitted at rest in Neon**.
- [ ] **API-1.2.5**: Fetch profile again via `GET /users/me` using `TOKEN_A`:
  ```bash
  curl -X GET "http://localhost:8000/users/me" -H "Authorization: Bearer $TOKEN_A"
  ```
  - **Expected Verification**: Returns fresh updated profile immediately (cache was evicted during `PUT`).
  - `health_profile.blood_type == "O-Positive"`
  - `health_profile.known_allergies == "Penicillin, Sulfa drugs"`
  - Transparent ORM decryption successfully recovered plaintext for the authenticated user.

---

### 1.3 Full Account Deletion & Cross-Table Cascade Hard-Delete
Verifies GDPR/HIPAA "Right to be Forgotten" compliance: deleting an account must physically wipe all documents, chat messages, semantic chunks, patient facts, and upload jobs from PostgreSQL, evict token cache, and nullify audit logs.

#### Test Steps
- [ ] **SETUP-1.3.1**: Seed active user with 1 document, 2 chat sessions, 4 messages, 2 patient facts, and 1 upload job.
- [ ] **API-1.3.2**: Issue account deletion request:
  ```bash
  curl -X DELETE "http://localhost:8000/users/me" \
    -H "Authorization: Bearer $TOKEN_A"
  ```
  - **Expected Status**: `204 No Content`
- [ ] **API-1.3.3**: Attempt to query `GET /users/me` with the previous `TOKEN_A`:
  ```bash
  curl -X GET "http://localhost:8000/users/me" -H "Authorization: Bearer $TOKEN_A"
  ```
  - **Expected Status**: `401 Unauthorized` (Token cache immediately revoked).
- [ ] **DB-1.3.4 (Merciless Cascade Check)**: Run the following zero-row audit in Neon:
  ```sql
  SELECT 'users' AS tbl, count(*) FROM users WHERE id = '<USER_UUID>'
  UNION ALL
  SELECT 'documents', count(*) FROM documents WHERE user_id = '<USER_UUID>'
  UNION ALL
  SELECT 'chats', count(*) FROM chats WHERE user_id = '<USER_UUID>'
  UNION ALL
  SELECT 'chat_documents', count(*) FROM chat_documents WHERE chat_id IN (SELECT id FROM chats WHERE user_id = '<USER_UUID>')
  UNION ALL
  SELECT 'chat_chunks', count(*) FROM chat_chunks WHERE user_id = '<USER_UUID>'
  UNION ALL
  SELECT 'patient_facts', count(*) FROM patient_facts WHERE user_id = '<USER_UUID>'
  UNION ALL
  SELECT 'upload_jobs', count(*) FROM upload_jobs WHERE user_id = '<USER_UUID>'
  UNION ALL
  SELECT 'dependent_profiles', count(*) FROM dependent_profiles WHERE user_id = '<USER_UUID>';
  ```
  - **Expected Verification**: **Every count must be exactly `0`**.
- [ ] **DB-1.3.5 (Audit Log Preservation)**:
  ```sql
  SELECT count(*) FROM audit_logs WHERE user_id IS NULL AND action_type = 'ACCOUNT_DELETED';
  ```
  - **Expected Verification**: Audit log record preserved with `user_id = NULL` (FK `ON DELETE SET NULL` satisfied).

---

## 2. Document Upload & Processing (The Two-Phase Pipeline)

### 2.1 Standard PDF Upload & Background Index State Transition
Verifies fast-path responsiveness (UI unlocks in ≤ 4 seconds via `local_ready`), async task queuing, background GCS sync, and metrics/summary pre-warming.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React Frontend
    participant API as FastAPI Backend
    participant DB as Neon PostgreSQL
    participant Disk as Local /tmp Disk
    participant GCS as Google Cloud Storage
    participant Gemini as Vertex AI

    User->>UI: Upload blood_test.pdf
    UI->>API: POST /upload (multipart/form-data)
    API->>DB: INSERT upload_jobs (status='processing')
    API->>Disk: Parse PDF & Build Local FAISS+BM25
    API->>DB: INSERT documents (index_status='local_ready')
    API-->>UI: 202 Accepted {job_id, document_id, status: 'processing'}
    UI->>API: Poll GET /upload/status/{job_id}
    Note over UI,API: ~3-4s: Status flips to 'ready'
    UI->>User: UI unlocks; chat & tabs active
    par Background Async Tasks
        API->>GCS: Upload indexes/user_X_doc_Y to GCS
        API->>DB: UPDATE documents SET index_status='synced'
        API->>Gemini: Prewarm Lab Metrics extraction
        API->>DB: UPDATE documents SET cached_metrics=[...]
        API->>Gemini: Prewarm Printable Summary
        API->>DB: UPDATE documents SET cached_summary='...'
    end
```

#### Test Steps
- [ ] **UI-2.1.1**: Log in and click the upload zone (`input[type="file"]`). Attach standard lab report PDF (`test_cbc_report.pdf`).
- [ ] **UI-2.1.2**: Start stopwatch. Verify progress indicator appears: *"Processing document..."*.
- [ ] **UI-2.1.3**: Confirm UI unlocks and document appears in sidebar in **≤ 4.5 seconds**.
- [ ] **DB-2.1.4 (Phase 1 DB Check)**: Immediately query Neon DB within 5 seconds of upload:
  ```sql
  SELECT id, filename, index_status, cached_metrics, cached_summary, created_at 
  FROM documents 
  WHERE filename = 'test_cbc_report.pdf' 
  ORDER BY created_at DESC LIMIT 1;
  ```
  - **Expected**: `index_status = 'local_ready'`.
- [ ] **DB-2.1.5 (Phase 2 DB Check)**: Wait 15 seconds for background tasks to complete and re-query:
  ```sql
  SELECT index_status, 
         (cached_metrics IS NOT NULL) AS has_metrics, 
         (cached_summary IS NOT NULL AND length(cached_summary) > 50) AS has_summary
  FROM documents 
  WHERE id = '<DOCUMENT_UUID>';
  ```
  - **Expected**: `index_status = 'synced'`; `has_metrics = true`; `has_summary = true`.
- [ ] **API-2.1.6**: Verify upload job status endpoint:
  ```bash
  curl -X GET "http://localhost:8000/upload/status/<JOB_ID>" -H "Authorization: Bearer $TOKEN"
  ```
  - **Expected Status**: `200 OK`
  - **Expected JSON**: `{"status": "ready", "document_id": "<DOCUMENT_UUID>", "error": null}`.

---

### 2.2 Invalid File Upload & Error Boundaries
Verifies file magic byte rejection, non-PDF filtering, inline UI banner presentation without generic toasts, and strict zero-row database persistence.

#### Test Steps
- [ ] **UI-2.2.1**: Attempt to upload a text file: `malicious_script.txt` (or a `.pdf` file with corrupted non-`%PDF-` header).
- [ ] **UI-2.2.2**: Verify that **no toast** notification pops up.
- [ ] **UI-2.2.3**: Verify an **inline error banner** appears with red styling above the input field:
  - Text contains: *"File must be a valid PDF format."* (or *"The uploaded file is empty or corrupted."*).
- [ ] **DB-2.2.4 (Zero DB Mutation Check)**:
  ```sql
  SELECT count(*) FROM documents WHERE filename LIKE '%malicious_script%';
  SELECT count(*) FROM upload_jobs WHERE filename LIKE '%malicious_script%';
  ```
  - **Expected**: Exactly **`0` rows** across both tables.

---

### 2.3 Document Deletion & Purge of Physical Indexes
Verifies that deleting a document cleans up all database rows, in-memory retriever cache, local `/tmp` index files, and Google Cloud Storage index blobs.

#### Test Steps
- [ ] **UI-2.3.1**: In the left sidebar, hover over the uploaded document.
- [ ] **UI-2.3.2**: Click the trash can icon (`[data-testid="delete-doc-button"]`).
- [ ] **UI-2.3.3**: In the confirmation dialog, click **"Delete"**.
- [ ] **UI-2.3.4**: Verify the document disappears from the sidebar list immediately.
- [ ] **DB-2.3.5**: Inspect Neon database:
  ```sql
  SELECT count(*) FROM documents WHERE id = '<DOCUMENT_UUID>';
  SELECT count(*) FROM chats WHERE document_id = '<DOCUMENT_UUID>';
  SELECT count(*) FROM chat_documents WHERE document_id = '<DOCUMENT_UUID>';
  ```
  - **Expected**: All counts equal **`0`**.
- [ ] **FS-2.3.6 (Index Cleanup)**: Verify local disk index directory no longer exists:
  - Path: `backend/indexes/user_<USER_UUID>_doc_<DOCUMENT_UUID>.index` or `/tmp/...` must **NOT exist**.

---

## 3. RAG & AI Chat Persistence

### 3.1 Document-Grounded Q&A & Fernet Chat Persistence
Verifies streaming SSE token delivery, response grounding from PDF chunks, and symmetric Fernet encryption at rest for each message turn in `chats.message`.

#### Test Steps
- [ ] **UI-3.1.1**: Select document `test_cbc_report.pdf` in the sidebar.
- [ ] **UI-3.1.2**: Enter query in chat box: *"What is my Hemoglobin level and is it normal?"*. Press Enter.
- [ ] **UI-3.1.3**: Observe real-time SSE stream. Verify tokens stream continuously without blocking.
- [ ] **UI-3.1.4**: Verify response references document text (e.g., *"Your Hemoglobin is 14.2 g/dL, which falls within the normal reference range..."*).
- [ ] **UI-3.1.5**: Verify medical disclaimer is appended at the end of the AI response.
- [ ] **DB-3.1.6 (Raw SQL Encryption Check)**:
  ```sql
  SELECT id, role, message, session_id, session_title 
  FROM chats 
  WHERE document_id = '<DOCUMENT_UUID>' 
  ORDER BY created_at ASC;
  ```
  - **Expected Row 1 (`role='user'`)**:
    - `message` **MUST start with `gAAAAA`** in raw SQL.
    - `session_id = 'doc-<DOCUMENT_UUID>'` (or dedicated UUID).
  - **Expected Row 2 (`role='assistant'`)**:
    - `message` **MUST start with `gAAAAA`** in raw SQL.
- [ ] **API-3.1.7 (Decryption Verification)**:
  ```bash
  curl -X GET "http://localhost:8000/users/me/chats?document_id=<DOCUMENT_UUID>" \
    -H "Authorization: Bearer $TOKEN"
  ```
  - **Expected Verification**: The returned JSON contains plaintext for both messages:
    - User: `"What is my Hemoglobin level and is it normal?"`
    - Assistant: `"Your Hemoglobin is 14.2 g/dL..."`

---

### 3.2 Standalone General Health & Long-Term Patient Memory
Verifies that conversations without documents persist durable `session_id` and `session_title`, auto-extract active `PatientFact` rows, and recall them across browser reloads.

#### Test Steps
- [ ] **UI-3.2.1**: Click **"New Chat"** (no document attached).
- [ ] **UI-3.2.2**: Send message: *"I was diagnosed with Type 2 Diabetes last month and take Metformin 500mg daily."*.
- [ ] **UI-3.2.3**: Verify AI answers with medication lifestyle guidance.
- [ ] **DB-3.2.4 (Fact Extraction Verification)**: Wait 3 seconds for async memory extraction:
  ```sql
  SELECT id, fact_type, fact_text, source_type, is_active, confidence 
  FROM patient_facts 
  WHERE user_id = '<USER_UUID>' AND is_active = true;
  ```
  - **Expected**: At least 2 active facts extracted:
    - `fact_type = 'condition'`, decrypted text contains *"Type 2 Diabetes"*
    - `fact_type = 'medication'`, decrypted text contains *"Metformin 500mg"*
    - `source_type = 'chat'`
    - `source_id = '<CHAT_MESSAGE_UUID>'`
- [ ] **UI-3.2.5 (Reload & Recall)**: Hard refresh browser tab (`Ctrl+F5` / `Cmd+Shift+R`).
- [ ] **UI-3.2.6**: In the same conversation session, ask: *"What medications am I currently taking?"*.
- [ ] **UI-3.2.7**: Verify AI response explicitly cites *"Metformin 500mg"* based on retrieved memory context, even though it was not repeated in the prompt.

---

### 3.3 Cross-Session & Cross-Dependent Isolation (Zero Bleed Test)
Verifies that memory facts, chat history, and retrieval indexes from Document A never contaminate Document B, a separate standalone session, or a Dependent Profile.

#### Test Matrix

| Source Context | Injected Sensitive Fact | Target Context To Query | Negative Assertion (Must NOT Appear) |
|---|---|---|---|
| **Document A** (Cardiology) | Troponin I = 0.45 ng/mL | **Document B** (Lipid Panel) | No mention of Troponin or cardiac enzymes |
| **User Profile (Self)** | Chronic Migraines | **Dependent Profile** (Child) | Child's health profile has 0 migraine facts |
| **Standalone Session 1** | Penicillin anaphylaxis | **Standalone Session 2** | `GET /users/me/chats?session_id=sess-2` contains 0 sess-1 messages |

#### Test Steps
- [ ] **UI-3.3.1**: Create a Dependent Profile: *"Junior"* (Child, Age 8) via Settings -> Dependents.
- [ ] **UI-3.3.2**: Select *"Junior"* in the Patient Context selector.
- [ ] **UI-3.3.3**: Send message: *"Junior has a peanut allergy."*.
- [ ] **DB-3.3.4 (Dependent Isolation in DB)**:
  ```sql
  SELECT dependent_id, fact_text 
  FROM patient_facts 
  WHERE user_id = '<USER_UUID>';
  ```
  - **Expected**: Peanut allergy row has `dependent_id = '<JUNIOR_UUID>'`.
  - Self-records have `dependent_id IS NULL`.
- [ ] **UI-3.3.5**: Switch context back to *"Self"*. Ask: *"What allergies do I have?"*.
- [ ] **UI-3.3.6**: Verify AI reports only Self allergies (Penicillin), with **zero mention of peanut allergy**.

---

## 4. Clinical Artifacts (Metrics & Summaries)

### 4.1 Lab Metrics Extraction & Cache Validation
Verifies sub-300ms retrieval of pre-warmed clinical biomarker metrics, proper status badges, and cache-busting behavior on "Force Refresh".

#### Test Steps
- [ ] **UI-4.1.1**: Open document `test_cbc_report.pdf`.
- [ ] **UI-4.1.2**: Click the **"Lab Metrics"** tab at the top of the chat view.
- [ ] **PERF-4.1.3**: Open browser DevTools Network tab. Filter for `/extract-metrics`.
  - **Latency Assertion**: Response duration must be **< 300 ms** (cache hit from pre-warming).
- [ ] **UI-4.1.4**: Verify the rendered table columns:
  - `Test / Analyte Name` (e.g., Hemoglobin, WBC, Platelets)
  - `Result Value` (e.g., 14.2)
  - `Reference Range` (e.g., 13.5 - 17.5 g/dL)
  - `Status Badge` (`NORMAL`, `HIGH`, or `LOW` with color coding)
- [ ] **DB-4.1.5**: Check Neon DB:
  ```sql
  SELECT (cached_metrics IS NOT NULL) AS is_cached, jsonb_array_length(cached_metrics::jsonb) AS metric_count
  FROM documents 
  WHERE id = '<DOCUMENT_UUID>';
  ```
  - **Expected**: `is_cached = true`; `metric_count >= 3`.
- [ ] **UI-4.1.6**: Click **"Force Refresh"** button.
- [ ] **PERF-4.1.7**: Observe network request: `/extract-metrics?force_refresh=true`.
  - Takes 1.5 - 3.5s (LLM re-extraction runs and commits fresh JSON to `documents.cached_metrics`).

---

### 4.2 Printable Physician Summary & Print Layout
Verifies cached Markdown summary retrieval, emoji stripping, specialist recommendation routing, and browser print stylesheet formatting.

#### Test Steps
- [ ] **UI-4.2.1**: While viewing a document, click the **"Print Doctor Summary"** button (`[data-testid="print-summary-button"]`).
- [ ] **PERF-4.2.2**: Verify network call to `/users/me/documents/{document_id}/summary` returns in **< 200 ms** with `{"cached": true, "summary": "..."}`.
- [ ] **UI-4.2.3**: Inspect summary modal text:
  - Header: Clinical Overview
  - Sections: Abnormal Findings, System Review, Physician Next Steps
  - **Emoji Verification**: Zero emojis present in summary text (verified by backend `strip_emojis` sanitizer).
- [ ] **UI-4.2.4**: Click **"Print Summary"** button.
- [ ] **UI-4.2.5**: Verify `@media print` CSS:
  - Left navigation sidebar is hidden (`display: none`).
  - Chat input controls are hidden.
  - Printable summary takes 100% page width with crisp high-contrast black-on-white typography.

---

### 4.3 "Try a Sample Report" Flow
Verifies new-user onboarding: clicking sample report loads pre-packaged clinical PDF, sets auto-title, and executes initial clinical inquiry.

#### Test Steps
- [ ] **UI-4.3.1**: Log in to a clean account with 0 documents.
- [ ] **UI-4.3.2**: On the welcome screen, click **"Try with a Sample Blood Test Report"**.
- [ ] **UI-4.3.3**: Verify the application attaches a sample report (e.g., `Sample_Report.pdf`).
- [ ] **UI-4.3.4**: Verify the chat title in the sidebar is automatically formatted as:
  - `Sample Report: [Panel Name]` (e.g., `Sample Report: Lipid Panel` or `Sample Report: CBC`).
- [ ] **UI-4.3.5**: Verify initial query is automatically submitted: *"Can you summarize the abnormal findings in this report?"*.
- [ ] **DB-4.3.6**: Verify Neon database has stored the sample document and chat:
  ```sql
  SELECT id, title, filename FROM documents WHERE title LIKE 'Sample Report:%' ORDER BY created_at DESC LIMIT 1;
  ```
  - **Expected**: Exactly 1 matching row exists with `title = 'Sample Report: ...'`.

---

## 5. UI State & Edge Cases

### 5.1 Mid-Stream Query Abort & Disconnect Resilience
Verifies that when a user abruptly closes the browser tab, navigates away, or clicks "Stop", the backend gracefully cancels generation, rolls back or marks the turn `[interrupted]`, and leaks zero Neon connection pool slots.

#### Test Steps
- [ ] **UI-5.1.1**: Ask a complex clinical question: *"Provide a detailed comprehensive differential diagnosis for persistent microcytic anemia..."*.
- [ ] **UI-5.1.2**: While tokens are actively streaming (~2 seconds in), click the **"Stop Generating"** button (or immediately close browser tab / trigger `AbortController.abort()`).
- [ ] **SRV-5.1.3**: Inspect backend FastAPI logs:
  - Verify log message: `Client disconnected or query stream cancelled for user_id=..., chat_id=...`.
  - Verify task cancellation: `stream_task.cancel()`.
- [ ] **DB-5.1.4 (Orphaned Row Check)**:
  ```sql
  SELECT id, role, message FROM chats WHERE user_id = '<USER_UUID>' ORDER BY created_at DESC LIMIT 2;
  ```
  - **Case A (Tokens were yielded before abort)**: Assistant row exists with suffix `[interrupted]` to preserve conversational coherence.
  - **Case B (Aborted before first token)**: Unanswered user row was cleanly deleted; **zero orphaned unanswered user rows remain in DB**.
- [ ] **DB-5.1.5 (Connection Pool Check)**: Check active connections in Neon:
  ```sql
  SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%';
  ```
  - **Expected**: No stranded active transactions or connection leaks.

---

### 5.2 Mobile Viewport Responsiveness (375 × 812 px)
Verifies responsive UI integrity, DeepSeek-style drawer animation, horizontal viewport stability, and table scrolling on iOS/Android viewports.

#### Test Steps
- [ ] **UI-5.2.1**: Set browser emulation to **375px × 812px** (iPhone 13 / Mini / X viewport).
- [ ] **UI-5.2.2**: Verify the sidebar is collapsed by default on initial render.
- [ ] **UI-5.2.3**: Click the floating toggle button. Verify sidebar slides smoothly over content (`translate-x-0`) with a dark backdrop.
- [ ] **UI-5.2.4**: Click the backdrop. Verify sidebar slides away (`-translate-x-full`).
- [ ] **DOM-5.2.5 (Zero Horizontal Window Overflow)**: Run in browser console:
  ```javascript
  document.documentElement.scrollWidth <= window.innerWidth
  ```
  - **Expected**: `true` (Page must never scroll horizontally).
- [ ] **UI-5.2.6 (Lab Metrics Table Containment)**: Navigate to Lab Metrics tab.
  - Verify table wrapper has `overflow-x-auto` allowing the data table to scroll horizontally inside its card container without pushing the main page viewport.

---

### 5.3 Multi-Language Internationalization (English ⇄ Hindi)
Verifies full interface localization, persistent language preference, and localized error messages.

#### Test Steps
- [ ] **UI-5.3.1**: Open Settings modal (`[data-testid="settings-button"]`).
- [ ] **UI-5.3.2**: Under **"App Interface Language"**, select **"Hindi (हिंदी)"**.
- [ ] **UI-5.3.3**: Click **"Save Changes"**.
- [ ] **UI-5.3.4**: Verify UI strings update immediately:
  - Sidebar: *"New Chat"* updates to Hindi translation.
  - Input placeholder: updates to *"अपनी रिपोर्ट के बारे में कोई भी प्रश्न पूछें..."*.
- [ ] **STORAGE-5.3.5**: Inspect browser local storage:
  - `localStorage.getItem('mediskye_ui_lang') === 'hi'`.
- [ ] **DB-5.3.6**: Check backend user profile:
  ```sql
  SELECT language_preference FROM users WHERE id = '<USER_UUID>';
  ```
  - **Expected**: `language_preference = 'Hindi'`.

---

## 6. Persistence Verification (The "Loose Ends" Audit Queries)

The executing QA AI must run this merciless SQL audit suite directly against Neon PostgreSQL at the conclusion of all test flows. **Every query must return 0 rows** (or match the specified clean-state assertion).

### 6.1 Orphaned Chat Records
Verifies no chat rows point to non-existent users or deleted documents (unless deliberately null for general chat):
```sql
-- Query 6.1: Orphaned chats with invalid user_id
SELECT c.id, c.user_id, c.message 
FROM chats c 
LEFT JOIN users u ON c.user_id = u.id 
WHERE u.id IS NULL;
-- EXPECTED: 0 rows

-- Query 6.2: Chats with dangling non-null document_id
SELECT c.id, c.document_id, c.message 
FROM chats c 
LEFT JOIN documents d ON c.document_id = d.id 
WHERE c.document_id IS NOT NULL AND d.id IS NULL;
-- EXPECTED: 0 rows
```

### 6.2 Orphaned Chat Chunks & Semantic Chunks
Verifies that deleting chats or users removed all embedding chunks:
```sql
-- Query 6.3: Dangling ChatChunks without parent Chat
SELECT cc.id, cc.chat_id 
FROM chat_chunks cc 
LEFT JOIN chats c ON cc.chat_id = c.id 
WHERE c.id IS NULL;
-- EXPECTED: 0 rows
```

### 6.3 Orphaned Chat Documents (Pivot Links)
Verifies no multi-document pivot links point to missing documents or chats:
```sql
-- Query 6.4: Dangling ChatDocument links
SELECT cd.id, cd.chat_id, cd.document_id 
FROM chat_documents cd 
LEFT JOIN chats c ON cd.chat_id = c.id 
LEFT JOIN documents d ON cd.document_id = d.id 
WHERE c.id IS NULL OR d.id IS NULL;
-- EXPECTED: 0 rows
```

### 6.4 Orphaned Patient Facts
Verifies that patient facts whose source chat was deleted have been physically cascade-deleted:
```sql
-- Query 6.5: Dangling PatientFacts where source chat no longer exists
SELECT pf.id, pf.source_type, pf.source_id, pf.fact_text 
FROM patient_facts pf 
WHERE pf.source_type = 'chat' 
  AND pf.source_id IS NOT NULL 
  AND pf.source_id NOT IN (SELECT id::text FROM chats);
-- EXPECTED: 0 rows
```

### 6.5 Orphaned Upload Jobs
Verifies no upload jobs point to deleted users:
```sql
-- Query 6.6: Dangling UploadJobs
SELECT uj.id, uj.user_id, uj.status 
FROM upload_jobs uj 
LEFT JOIN users u ON uj.user_id = u.id 
WHERE u.id IS NULL;
-- EXPECTED: 0 rows
```

### 6.6 Missing Foreign Key Constraint Verification
Verifies that database constraints defined in `models.py` are enforced in PostgreSQL schema:
```sql
-- Query 6.7: Verify foreign key definitions on critical child tables
SELECT
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc 
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints AS rc
  ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_name IN ('documents', 'chats', 'patient_facts', 'chat_chunks', 'audit_logs')
ORDER BY tc.table_name;
```
- **Expected Verification**:
  - `documents.dependent_id` -> `delete_rule = 'SET NULL'`
  - `audit_logs.dependent_id` -> `delete_rule = 'SET NULL'`
  - `chats.user_id` -> `delete_rule = 'CASCADE'`
  - `patient_facts.user_id` -> `delete_rule = 'CASCADE'`
  - `chat_chunks.chat_id` -> `delete_rule = 'CASCADE'`

---

## 7. Master Test Execution Sign-Off Matrix

The executing QA Agent must record timestamps, test results, and final hash signatures in this matrix:

| Section | Target Component | Status (`PASS` / `FAIL`) | Executed At (UTC) | Agent Notes |
|---|---|---|---|---|
| **1.1** | Sign Up & User Provisioning | `[ ]` | | |
| **1.2** | Profile Update & Fernet PHI | `[ ]` | | |
| **1.3** | Account Deletion Cascade | `[ ]` | | |
| **2.1** | Two-Phase PDF Upload Pipeline | `[ ]` | | |
| **2.2** | Invalid File Rejection | `[ ]` | | |
| **2.3** | Document Deletion & Index Purge| `[ ]` | | |
| **3.1** | Document QA & Encrypted Chats | `[ ]` | | |
| **3.2** | General Health Memory Recall | `[ ]` | | |
| **3.3** | Zero Cross-Session Bleed | `[ ]` | | |
| **4.1** | Lab Metrics Sub-300ms Cache | `[ ]` | | |
| **4.2** | Printable Physician Summary | `[ ]` | | |
| **4.3** | Sample Report Onboarding Flow | `[ ]` | | |
| **5.1** | Mid-Stream Abort & No Stranded Rows | `[ ]` | | |
| **5.2** | Mobile Viewport Responsiveness | `[ ]` | | |
| **5.3** | Multi-Language i18n Switch | `[ ]` | | |
| **6.0** | Complete Loose Ends SQL Audit | `[ ]` | | |

> **Sign-Off Statement**:  
> *"All 16 sections executed against live Neon PostgreSQL and ASGI API. Zero orphaned rows, zero unencrypted PHI at rest, and zero memory bleed detected across the full system lifecycle."*

