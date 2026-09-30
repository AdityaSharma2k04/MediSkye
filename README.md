# MediSkye

**Making medical reports understandable for everyone.**

MediSkye is an AI-powered healthcare assistant that helps patients interpret diagnostic PDF reports — blood tests, lipid panels, imaging summaries, and more — in plain language. Upload a report, ask follow-up questions, and get cautious, context-grounded explanations powered by retrieval-augmented generation (RAG).

> **Disclaimer:** MediSkye is for educational and informational purposes only. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider.

---

## Table of contents

- [Live demo](#live-demo)
- [What MediSkye does](#what-mediskye-does)
- [System architecture](#system-architecture)
- [End-to-end workflow](#end-to-end-workflow)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Production deployment](#production-deployment)
- [Security & reliability](#security--reliability)
- [Enhancements shipped](#enhancements-shipped)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## Live demo

| Service | URL |
|---------|-----|
| **Frontend** (React + Vite) | [mediskye-react.vercel.app](https://mediskye-react.vercel.app) (Example) |
| **Backend** (FastAPI) | [mediskye-51pi.onrender.com](https://mediskye-51pi.onrender.com) |

<p align="center">
  <img width="900" alt="MediSkye screenshot" src="https://github.com/user-attachments/assets/10db611d-cb09-4bd6-bf4c-7e563b9f10b4" />
</p>

---

## What MediSkye does

Millions of people receive lab results but struggle to understand them. MediSkye closes that gap by:

1. **Extracting text** from uploaded medical PDFs (text-based, layout-heavy, or scanned).
2. **Indexing the report** into a searchable vector store (FAISS + Google embeddings).
3. **Retrieving relevant sections** when you ask a question (MMR search over report chunks).
4. **Generating a plain-language answer** with Gemini Flash (`gemini-flash-latest`), grounded in your report.
5. **Applying safety guardrails** — emergency detection, no definitive diagnoses, mandatory disclaimers.

**Typical questions MediSkye can help with:**

- "Is my hemoglobin within the normal range?"
- "What does elevated LDL cholesterol mean?"
- "Can you explain my liver function test results?"

---

## System architecture

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        UI["React Frontend<br/>Vite / Tailwind"]
    end

    subgraph API["API Layer — FastAPI"]
        UP["POST /upload"]
        Q["POST /query"]
        G["guards.py<br/>auth · size · PDF check"]
        RL["slowapi<br/>rate limiting"]
    end

    subgraph RAG["RAG Pipeline"]
        L["loader.py<br/>PyPDF2 → PyMuPDF → OCR"]
        E["embedder.py<br/>Google gemini-embedding-2"]
        R["retriever.py<br/>FAISS + MMR k=8"]
        P["prompt_builder.py"]
        S["safety.py<br/>emergency · disclaimer"]
    end

    subgraph External["External Services"]
        GEM["Google Gemini Flash"]
    end

    subgraph Store["Session Store (in-memory)"]
        VS[("vectorstores[session_id]")]
    end

    UI -->|"PDF + X-Session-ID"| UP
    UI -->|"JSON query + session_id"| Q
    UP --> G --> RL --> L --> E --> R
    L --> VS
    Q --> G --> RL --> S
    S -->|"emergency?"| UI
    Q --> R --> VS
    R --> P --> GEM --> S --> UI
```

---

## End-to-end workflow

### Upload workflow

```mermaid
sequenceDiagram
    actor User
    participant ST as React UI
    participant API as FastAPI Backend
    participant Guard as guards.py
    participant Load as loader.py
    participant Ret as retriever.py

    User->>ST: Upload PDF report
    ST->>ST: Generate / reuse session_id (UUID)
    ST->>API: POST /upload<br/>file + X-Session-ID + X-API-Key

    API->>Guard: Validate API key (if configured)
    Guard->>Guard: Check PDF magic bytes (%PDF)
    Guard->>Guard: Enforce max file size

    API->>Load: Extract text (PyPDF2 → PyMuPDF → OCR)
    alt Extraction fails [under 100 chars]
        Load-->>API: PDFExtractionError
        API-->>ST: HTTP 422 + clear message
    else Extraction succeeds
        Load->>Ret: Chunk pages → embed → FAISS index
        Ret->>API: Store in vectorstores[session_id]
        API-->>ST: 200 OK
        ST-->>User: Report ready for questions
    end
```

### Query workflow

```mermaid
sequenceDiagram
    actor User
    participant ST as React UI
    participant API as FastAPI Backend
    participant Safe as safety.py
    participant Ret as retriever.py
    participant LLM as Gemini Flash

    User->>ST: Type medical question
    ST->>API: POST /query<br/>{ session_id, query }

    API->>Safe: Check emergency keywords
    alt Emergency detected
        Safe-->>ST: Call emergency services message
    else Normal query
        API->>Ret: MMR search (k=8, fetch_k=24)
        Ret->>API: Top chunks with page metadata
        API->>LLM: Grounded prompt + report excerpts
        LLM->>Safe: Append medical disclaimer
        Safe-->>ST: Final response
        ST-->>User: Display in chat history
    end
```

---

## Tech stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React + Vite + Tailwind | Upload UI, chat interface, session management |
| Backend | [FastAPI](https://fastapi.tiangolo.com/) | REST API, validation, middleware |
| LLM | Gemini Flash (`gemini-flash-latest`) | Plain-language medical explanations |
| Embeddings | Google `gemini-embedding-2` | Vector encoding for RAG |
| Vector DB | FAISS | Similarity search over report chunks |
| Retrieval | MMR (Max Marginal Relevance) | Diverse, relevant chunk selection |
| PDF parsing | PyPDF2, PyMuPDF, Tesseract OCR | Text + layout + scanned PDF support |
| Rate limiting | slowapi | Abuse and cost protection |
| Deployment | Render (API) + Vercel (UI) | Production hosting |

---

## Project structure

```
MediSkye/
├── backend/
│   ├── main.py                 # FastAPI app — /upload, /query
│   ├── start.sh                # Render start command
│   ├── requirements.txt
│   └── rag/
│       ├── loader.py           # Tiered PDF extraction
│       ├── embedder.py         # Google Generative AI embeddings
│       ├── retriever.py        # FAISS index + MMR retrieval
│       ├── prompt_builder.py   # Grounded LLM prompts
│       ├── guards.py           # Auth, upload limits, PDF validation
│       └── safety.py           # Emergency gate + disclaimers
├── frontend/
│   ├── src/                    # React components and pages
│   ├── package.json            # Node dependencies
│   └── vite.config.js          # Vite configuration
├── .env                        # Local secrets (not committed)
├── .gitignore
└── README.md
```

---

## Getting started

### Prerequisites

- **Python 3.10+**
- **Google API key** with Gemini API enabled — [Get one here](https://aistudio.google.com/apikey)
- **Git**
- **Optional:** [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for scanned/image-based PDFs

### 1. Clone the repository

```bash
git clone https://github.com/Ujjwal0207/MediSkye.git
cd MediSkye
```

### 2. Configure environment

Create a `.env` file in the **project root**:

```env
GOOGLE_API_KEY=your-google-api-key

# Recommended for production
MEDISKYE_API_KEY=your-shared-secret-key
MEDISKYE_MAX_UPLOAD_MB=10
```

### 3. Run the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at **http://localhost:8000**. Interactive API docs: **http://localhost:8000/docs**.

### 4. Run the frontend (new terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend opens at **http://localhost:3000**.

### 5. Use the app

1. Open the React UI in your browser.
2. Upload a PDF medical report.
3. Wait for the success confirmation.
4. Ask a question about your report.
5. Review the AI response and chat history.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Google Generative AI key for Gemini + embeddings |
| `MEDISKYE_API_KEY` | No | — | Shared API key; when set, all requests must send `X-API-Key` |
| `MEDISKYE_MAX_UPLOAD_MB` | No | `10` | Maximum PDF upload size in megabytes |
| `MEDISKYE_API_URL` | No | Render URL | Backend URL used by the Streamlit frontend |

### Frontend deployment (production)

Configure your production API URL in your frontend's environment or `api.js` to point to `https://mediskye-51pi.onrender.com`.

### Render environment (production backend)

Set `GOOGLE_API_KEY`, `MEDISKYE_API_KEY`, and optionally `MEDISKYE_MAX_UPLOAD_MB` in the Render dashboard.

---

## API reference

### `POST /upload`

Upload and index a medical PDF for the current session.

**Headers**

| Header | Required | Description |
|--------|----------|-------------|
| `X-Session-ID` | Yes | UUID v4 session identifier |
| `X-API-Key` | If configured | Must match `MEDISKYE_API_KEY` |

**Body:** `multipart/form-data` with field `file` (PDF)

**Rate limit:** 5 requests / minute / IP

**Success (200)**

```json
{ "message": "PDF uploaded and processed successfully." }
```

**Errors:** `400` invalid PDF · `401` bad API key · `413` file too large · `422` extraction failed · `429` rate limited

---

### `POST /query`

Ask a question about the uploaded report.

**Headers**

| Header | Required | Description |
|--------|----------|-------------|
| `X-API-Key` | If configured | Must match `MEDISKYE_API_KEY` |

**Body (JSON)**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "Is my hemoglobin normal?"
}
```

**Rate limit:** 20 requests / minute / IP

**Success (200)**

```json
{
  "response": "Your hemoglobin is ... **Disclaimer:** This response is for educational purposes only..."
}
```

**Errors:** `400` invalid session · `401` bad API key · `429` rate limited · `{ "error": "No PDF uploaded yet for this session." }`

---

## Production deployment

### Backend — Render

1. Create a **Web Service** connected to this repo.
2. Set **Root Directory** to `backend`.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (see table above).
6. **Optional (OCR):** Add Tesseract to the build environment for scanned PDF support.

### Frontend — Vercel or Netlify

1. Connect your GitHub repository to Vercel/Netlify.
2. Set the build command to `npm run build` and output directory to `dist`.
3. Update the API base URL in `src/services/api.js` to your deployed backend URL.

### Production checklist

- [ ] `GOOGLE_API_KEY` set on Render
- [ ] API URL updated in the React frontend
- [ ] `MEDISKYE_MAX_UPLOAD_MB` configured appropriately
- [ ] Tesseract installed if expecting scanned PDFs
- [ ] CORS origins tightened if you add a custom domain (currently `*`)

---

## Security & reliability

| Feature | Implementation |
|---------|----------------|
| Session isolation | Each browser session gets a UUID; vector stores are keyed by `session_id` |
| Query privacy | Questions sent via `POST` JSON body — never in URL query strings |
| API authentication | Optional shared key via `X-API-Key` header |
| Upload validation | PDF magic-byte check + configurable size limit |
| Rate limiting | 5 uploads/min, 20 queries/min per IP |
| Medical safety | Emergency keyword short-circuit, cautious prompts, mandatory disclaimer |
| Temp file cleanup | Uploaded PDFs deleted after processing |
| Extraction guard | Fails loudly if PDF yields insufficient text (no silent empty index) |

**Known limitation:** Vector stores are in-memory and reset on server restart or Render cold start. Users must re-upload after a cold start. Persistent storage is planned.

---

## Enhancements shipped

MediSkye has gone through two major hardening passes:

### Enhancement 1 — Security & medical safety

| Area | Improvement |
|------|-------------|
| Multi-user privacy | Per-session vector stores instead of one shared global index |
| Query privacy | Switched from `GET /query` to `POST /query` with JSON body |
| Disk hygiene | Temp PDF files deleted after every upload |
| Medical safety | Emergency detection, safer prompts (no definitive diagnoses), mandatory disclaimer on every response |

### Enhancement 2 — Production guards & RAG quality

| Area | Improvement |
|------|-------------|
| API protection | Optional API key auth, rate limiting, PDF validation, upload size caps |
| PDF extraction | Tiered pipeline: PyPDF2 → PyMuPDF → Tesseract OCR fallback |
| Empty PDF handling | HTTP 422 error when extraction yields too little text |
| Chunking | Increased to 1200 chars / 200 overlap with page metadata preserved |
| Retrieval | MMR search with 8 diverse chunks (was 3 similar chunks) |
| Documentation | README aligned with actual stack (`gemini-flash-latest`, `gemini-embedding-2`) |

**Curious about the RAG math?** Read our [Medical RAG Benchmarks](benchmarks.md) to see exactly why `1200/200` chunking and `MMR k=8` outperforms naive retrieval on complex lab reports.

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | AI report chatbot with RAG |
| **Phase 2** | Planned | Medical triage — emergency vs routine vs self-care |
| **Phase 3** | Planned | Doctor recommendation by specialty and location |
| **Phase 4** | Planned | Helper/assisted mode for elderly patients |
| **Phase 5** | Planned | Mobile apps and SMS/low-bandwidth access |

---

## Contributing

Contributions are welcome. To propose a change:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes and open a pull request.

Ideas we'd love help with: persistent vector storage, hybrid retrieval, triage logic, UI/UX improvements, and test coverage.

---

## License & disclaimer

MediSkye is intended for **educational and informational use**. It must not be used as a replacement for qualified medical professionals. The authors are not liable for medical decisions made based on AI-generated content.

Always seek advice from a licensed doctor for diagnosis and treatment.




cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000



cd frontend
npm install
npm run dev
# MediSkye
