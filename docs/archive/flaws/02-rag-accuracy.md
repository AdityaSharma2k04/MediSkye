# RAG & Accuracy

## 6. PyPDF2 struggles with real medical reports

**Location:** `backend/rag/loader.py`

**Problem:** Extraction uses PyPDF2 only. Many lab reports are scanned images or complex tables. PyPDF2 often returns empty or garbled text.

**Impact:** Silent failure — an empty or useless vector store is built with no user-visible error.

**Suggested fix:** Detect empty/minimal extracted text and return an error. Add OCR (Tesseract, Google Document AI, etc.) for image-based PDFs.

### Second enhancement — FIXED

**What was done:**
- Rewrote `backend/rag/loader.py` with a tiered extraction pipeline:
  1. **PyPDF2** — text-based PDFs.
  2. **PyMuPDF (`fitz`)** — better layout/table extraction when PyPDF2 yields little text.
  3. **Tesseract OCR** (`pdf2image` + `pytesseract`) — scanned/image PDF fallback.
- Picks whichever extractor returns the most readable text.
- Raises `PDFExtractionError` if total extracted text is below 100 characters (no more silent empty vector stores).
- `backend/main.py` returns HTTP 422 with a clear error message to the user.

**Verification:** Empty or scanned PDFs no longer silently succeed; user sees an explicit extraction failure message.

**Remaining limitation:** OCR requires Tesseract installed on the server (e.g. Render buildpack). Without it, scanned PDFs may still fail with a helpful error rather than building junk embeddings.

---

## 7. Small chunks can split clinical context

**Location:** `backend/rag/retriever.py`

**Problem:** `RecursiveCharacterTextSplitter` uses `chunk_size=500` and `chunk_overlap=50`. Lab values may be split from reference ranges, units, or section headers.

**Impact:** Retrieved chunks may lack the pairing needed to answer "is my hemoglobin normal?"

**Suggested fix:** Increase chunk size, use structure-aware splitting (by section/table), or preserve metadata (page, section) on each chunk.

### Second enhancement — FIXED

**What was done:**
- Increased `chunk_size` from 500 → **1200** and `chunk_overlap` from 50 → **200**.
- Added paragraph-aware separators: `["\n\n", "\n", ". ", "; ", ", ", " ", ""]`.
- Switched from `split_text()` to **`split_documents()`** so page metadata survives chunking.
- Loader now returns per-page `Document` objects with `metadata={"page": N, "source": "..."}`.
- `prompt_builder.py` includes `[Page N]` labels in context sent to the LLM.

**Verification:** Lab values and reference ranges are more likely to stay in the same chunk; prompts show page numbers for retrieved excerpts.

---

## 8. Only top-3 chunks retrieved

**Location:** `backend/rag/retriever.py` — `retrieve_relevant_docs(..., k=3)`

**Problem:** Only three similar chunks are passed to the LLM. Critical information elsewhere in a long report may never be retrieved.

**Impact:** Incomplete or wrong answers for multi-page reports.

**Suggested fix:** Increase `k`, add re-ranking, hybrid search (keyword + vector), or summarize the full report once and RAG over sections.

### Second enhancement — FIXED

**What was done:**
- Replaced plain `similarity_search(k=3)` with **`max_marginal_relevance_search`** (MMR re-ranking).
- Increased retrieval from **k=3** → **k=8** final chunks.
- Added **`fetch_k=24`** so MMR selects diverse, relevant chunks from a larger candidate pool.

**Verification:** Longer reports send up to 8 diverse chunks to the LLM instead of 3 similar ones, reducing missed context on multi-page reports.

**Remaining limitation:** Still vector-only retrieval — no keyword/hybrid search yet.

---

## 9. No metadata on document chunks

**Location:** `backend/rag/retriever.py`

**Problem:** Chunks are stored as plain `Document(page_content=chunk)` with no page numbers, section names, or source labels.

**Impact:** Harder to debug wrong answers; LLM cannot cite "page 2, lipid panel."

**Suggested fix:** Attach metadata when splitting (page index, approximate section) and include it in the prompt.

### Second enhancement — PARTIALLY FIXED

**What was done:** Page numbers added via loader + `split_documents()` + `[Page N]` in prompts.

**Still open:** Section names, table labels, test panel names — see #39.

---

## 10. README vs code model mismatch

**Location:** `README.md` vs `backend/main.py`

**Problem:** README claims **Gemini 1.5 Pro**; code uses **`models/gemini-1.5-flash`**.

**Impact:** Documentation misleads users and reviewers about capability and cost profile.

**Suggested fix:** Align README with actual model, or switch code to the documented model if that was the intent.

### Second enhancement — FIXED

**What was done:**
- Updated `README.md` to document **Gemini 1.5 Flash** (matching `backend/main.py`).
- Corrected embedder description to Google-only (removed incorrect OpenAI mention).
- Documented new modules (`guards.py`, `safety.py`) and env vars (`MEDISKYE_API_KEY`, `MEDISKYE_MAX_UPLOAD_MB`).
- Added Tesseract OCR as optional prerequisite for scanned PDFs.

**Verification:** README tech stack and Phase 1 description now match the codebase.

---

## 11. Embedder description mismatch

**Location:** `README.md` project structure section

**Problem:** README says embedder supports "OpenAI or Google embeddings"; implementation only uses Google (`embedder.py`).

**Suggested fix:** Update README or implement the documented dual-provider option.


### Second enhancement — FIXED

**What was done:**
- Updated `README.md` to document that the embedder only supports Google embeddings.
- Corrected embedder description to Google-only (removed incorrect OpenAI mention).
- Documented new modules (`guards.py`, `safety.py`) and env vars (`MEDISKYE_API_KEY`, `MEDISKYE_MAX_UPLOAD_MB`).
- Added Tesseract OCR as optional prerequisite for scanned PDFs.

**Verification:** README tech stack and Phase 1 description now match the codebase.

---

## 38. No hybrid / keyword retrieval

**Location:** `backend/rag/retriever.py`

**Problem:** Retrieval is vector-only (MMR). Exact lab values and abbreviations (e.g. "HGB", "13.2 g/dL") may rank poorly in embedding space.

**Impact:** Wrong or missed chunks for value-specific questions.

**Suggested fix:** BM25 + vector hybrid search, or structured table extraction. See [future-plans](../future-plans/README.md).

**Status:** OPEN (pass 2 improved k and MMR; hybrid still missing)

---

## 39. Section-level metadata still missing

**Location:** `backend/rag/loader.py`, `backend/rag/retriever.py`

**Problem:** Pass 2 added page numbers but not section names (e.g. "Lipid Panel", "CBC"). Chunks cannot cite report sections.

**Impact:** LLM cannot reference "your lipid panel section" precisely.

**Suggested fix:** Parse section headers from PDF layout; attach `metadata["section"]`.

**Status:** OPEN (partial — page metadata only from pass 2)
