"""
PDF Loader with Vision-based table extraction.

Extraction pipeline (tiered):
  1. PyPDF2 — fast text extraction
  2. PyMuPDF — better layout handling
  3. Tesseract OCR — fallback for scanned PDFs
  4. Gemini Vision — for pages with complex tables/medical matrices

Pages detected as containing dense tables are rendered as images
and sent to Gemini Vision for structured Markdown extraction,
which preserves exact lab values that text extractors often scramble.
"""

import asyncio
import logging
import os

from langchain_core.documents import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)

from app.core.security import sanitize_text
from app.llm.gemini_client import call_gemini_with_retry

MIN_EXTRACTED_CHARS = 100


class PDFExtractionError(Exception):
    """Raised when a PDF yields too little readable text."""


def _char_count(docs: list[Document]) -> int:
    return sum(len(doc.page_content.strip()) for doc in docs)


# ─── Image Processing & Classification ───────────────────────────────────

async def classify_image_type(image_bytes: bytes) -> str:
    def _compress():
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        h, w = img.shape[:2]
        if max(h, w) > 512:
            scale = 512 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 30])
        return buffer.tobytes()

    compressed_bytes = await asyncio.to_thread(_compress)
    from google.genai.types import GenerateContentConfig, Part, ThinkingConfig

    try:
        image_part = Part.from_bytes(data=compressed_bytes, mime_type="image/jpeg")
        response = await call_gemini_with_retry(
            contents=["Respond with exactly one word: 'XRAY' if this is a radiological scan, or 'DOCUMENT' if this is a text-heavy clinical report.", image_part],
            config=GenerateContentConfig(
                thinking_config=ThinkingConfig(thinking_budget=0),
                temperature=0.0,
            ),
        )
        result = sanitize_text(response.text or "").strip().upper()
        if "XRAY" in result:
            return "XRAY"
        return "DOCUMENT"
    except Exception as e:
        logger.warning("Classification failed: %s", e)
        return "DOCUMENT"


async def process_image_path(image_type: str, image_bytes: bytes, source_meta: str) -> Document:
    if image_type == "XRAY":
        def _apply_clahe():
            import cv2
            import numpy as np
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return image_bytes
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced_l = clahe.apply(l_channel)
            merged = cv2.merge([enhanced_l, a_channel, b_channel])
            enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
            _, buffer = cv2.imencode(".png", enhanced)
            return buffer.tobytes()
        
        enhanced_bytes = await asyncio.to_thread(_apply_clahe)
        from google.genai.types import GenerateContentConfig, Part, ThinkingConfig

        try:
            image_part = Part.from_bytes(data=enhanced_bytes, mime_type="image/png")
            prompt = "You are an expert radiologist. Analyze this radiological scan and provide a detailed clinical observation summary. Be precise and medical."
            response = await call_gemini_with_retry(
                contents=[prompt, image_part],
                config=GenerateContentConfig(
                    thinking_config=ThinkingConfig(thinking_budget=0),
                    temperature=0.2,
                ),
            )
            text = sanitize_text(response.text or "").strip()
            return Document(page_content=text, metadata={"source": source_meta, "type": "xray"})
        except Exception as e:
            logger.warning("XRAY analysis failed: %s", e)
            return Document(page_content="", metadata={"source": source_meta, "type": "xray_error"})
    else:
        def _extract_ocr():
            try:
                import cv2
                import numpy as np
                import pytesseract
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    return ""
                text = pytesseract.image_to_string(img)
                return sanitize_text(text or "").strip()
            except Exception as e:
                logger.warning("OCR failed: %s", e)
                return ""
                
        text = await asyncio.to_thread(_extract_ocr)
        return Document(page_content=text, metadata={"source": source_meta, "type": "document"})


# ─── Standard Text Extractors ───────────────────────────────────────────

def _extract_with_pypdf2(pdf_path: str) -> list[Document]:
    reader = PdfReader(pdf_path)
    docs: list[Document] = []

    for index, page in enumerate(reader.pages, start=1):
        text = sanitize_text(page.extract_text() or "")
        if text:
            docs.append(Document(page_content=text, metadata={"page": index, "source": "pypdf2"}))

    return docs


def _safe_dpi(page, max_pixels: int = 25_000_000, target: int = 300) -> int:
    """Calculate safe DPI for rendering a page without exceeding max_pixels."""
    import math
    try:
        area_pt = max(page.rect.width * page.rect.height, 1.0)
        current_px = area_pt * ((target / 72.0) ** 2)
        if current_px <= max_pixels:
            return target
        scaled_dpi = int(72.0 * math.sqrt(max_pixels / area_pt))
        return max(scaled_dpi, 72)
    except Exception:
        return target


async def _extract_with_pymupdf(pdf_path: str) -> list[Document]:
    try:
        import pymupdf as fitz
    except ImportError:
        return []

    def _extract_pages_sync():
        pages_data = []
        with fitz.open(pdf_path) as pdf:
            for index, page in enumerate(pdf, start=1):
                text = sanitize_text(page.get_text() or "")
                if text and len(text) >= 50:
                    pages_data.append((index, "text", text))
                else:
                    pix = page.get_pixmap(dpi=_safe_dpi(page))
                    pages_data.append((index, "image", pix.tobytes("png")))
        return pages_data

    pages_data = await asyncio.to_thread(_extract_pages_sync)
    docs: list[Document] = []
    for index, kind, content in pages_data:
        if kind == "text":
            docs.append(Document(page_content=content, metadata={"page": index, "source": "pymupdf"}))
        else:
            image_type = await classify_image_type(content)
            doc = await process_image_path(image_type, content, source_meta="pymupdf_fallback")
            doc.metadata["page"] = index
            if doc.page_content and doc.page_content.strip():
                docs.append(doc)

    return docs


def _extract_with_ocr(pdf_path: str) -> list[Document]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return []

    try:
        pytesseract.get_tesseract_version()
    except Exception:
        return []

    docs: list[Document] = []
    try:
        images = convert_from_path(pdf_path)
    except Exception:
        return []

    for index, image in enumerate(images, start=1):
        text = sanitize_text(pytesseract.image_to_string(image) or "")
        if text:
            docs.append(Document(page_content=text, metadata={"page": index, "source": "ocr"}))

    return docs


# ─── Vision-based Table Detection & Extraction ──────────────────────────

def _detect_table_pages(pdf_path: str) -> list[int]:
    """
    Detect pages likely containing complex tables/medical matrices.
    Uses heuristics: high line-object count, embedded images, or
    low text-to-area ratio indicating tabular layout.
    
    Returns 0-indexed page numbers.
    """
    try:
        import pymupdf as fitz
    except ImportError:
        return []

    table_pages = []
    with fitz.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf):
            # Count drawing operations (lines/rects = table grid indicators)
            drawings = page.get_drawings()
            line_count = sum(1 for d in drawings if d.get("type") in ("l", "re", "s"))
            
            # Count images on the page (could be scanned tables)
            image_list = page.get_images(full=True)
            
            # Get text blocks for density analysis
            text_blocks = page.get_text("blocks")
            text_area = sum(
                (b[2] - b[0]) * (b[3] - b[1]) for b in text_blocks if b[6] == 0  # text blocks only
            )
            page_area = page.rect.width * page.rect.height
            text_density = text_area / page_area if page_area > 0 else 0
            
            # If the page already has clean, extractable text (>= 150 chars), digital extraction is preferred and complete
            text_extracted = (page.get_text() or "").strip()
            if len(text_extracted) >= 150:
                continue

            # Heuristics for scanned table detection:
            # - Many line/rect drawings (table borders) OR
            # - Has images AND low text density (scanned table) OR
            # - Text density is very low but page has content (complex layout)
            is_table_page = (
                line_count > 15 or  # Lots of grid lines
                (len(image_list) > 0 and text_density < 0.15) or  # Scanned content
                (line_count > 8 and text_density < 0.3)  # Moderate lines + sparse text
            )
            
            if is_table_page:
                table_pages.append(page_idx)

    return table_pages


def _enhance_image_clahe(image_bytes: bytes) -> bytes:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    to improve contrast of scanned medical documents before Vision AI.
    """
    try:
        import cv2
        import numpy as np
        
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return image_bytes
        
        # Convert to LAB color space
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # Apply CLAHE to the L channel
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced_l = clahe.apply(l_channel)
        
        # Merge back
        merged = cv2.merge([enhanced_l, a_channel, b_channel])
        enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
        
        # Encode back to PNG
        _, buffer = cv2.imencode(".png", enhanced)
        return buffer.tobytes()
    except ImportError:
        return image_bytes
    except Exception:
        return image_bytes


async def _extract_table_pages_with_vision(pdf_path: str, table_page_indices: list[int]) -> list[Document]:
    """
    Render flagged table pages as images, optionally enhance contrast,
    and send to Gemini Vision for structured Markdown extraction.
    Capped at MAX_VISION_PAGES = 20 with asyncio.Semaphore(3).
    """
    try:
        import pymupdf as fitz
        from google.genai.types import Part
    except ImportError:
        return []

    MAX_VISION_PAGES = 20
    indices_to_process = table_page_indices[:MAX_VISION_PAGES]
    semaphore = asyncio.Semaphore(3)

    VISION_PROMPT = """You are a precise medical document parser. Extract ALL content from this medical report page into well-structured Markdown.

Rules:
1. Preserve ALL numerical values exactly as shown (lab values, reference ranges, dates).
2. Format tables using Markdown table syntax with proper headers and alignment.
3. Include units (g/dL, mg/dL, mmol/L, etc.) exactly as shown.
4. If there are multiple tables, separate them with headers.
5. Include any notes, flags (H/L/Normal), or reference ranges.
6. Do NOT add any interpretation — only extract what is visible.

Output the structured Markdown extraction:"""

    async def _process_single_page(page_idx: int) -> Document | None:
        async with semaphore:
            def _render_and_fallback(p_idx):
                with fitz.open(pdf_path) as pdf:
                    if p_idx >= len(pdf):
                        return None, None
                    page = pdf[p_idx]
                    dpi = _safe_dpi(page)
                    pix = page.get_pixmap(dpi=dpi)
                    img_bytes = _enhance_image_clahe(pix.tobytes("png"))
                    fallback_text = sanitize_text(page.get_text() or "")
                    return img_bytes, fallback_text

            img_bytes, fallback_text = await asyncio.to_thread(_render_and_fallback, page_idx)
            if not img_bytes:
                return None

            try:
                # Send to Gemini Vision
                from google.genai.types import GenerateContentConfig, ThinkingConfig
                image_part = Part.from_bytes(data=img_bytes, mime_type="image/png")
                response = await call_gemini_with_retry(
                    contents=[VISION_PROMPT, image_part],
                    config=GenerateContentConfig(
                        thinking_config=ThinkingConfig(thinking_budget=0),
                        temperature=0.0,
                    ),
                )
                
                extracted_text = sanitize_text(response.text or "")
                if extracted_text and len(extracted_text) > 20:
                    return Document(
                        page_content=extracted_text,
                        metadata={
                            "page": page_idx + 1,
                            "source": "vision",
                            "extraction_method": "gemini_vision_table",
                        }
                    )
            except Exception as e:
                logger.warning("Vision extraction failed for page %s: %s", page_idx + 1, e)
                # Fall back to standard text for this page
                if fallback_text:
                    return Document(
                        page_content=fallback_text,
                        metadata={"page": page_idx + 1, "source": "pymupdf_fallback"}
                    )
            return None

    page_results = await asyncio.gather(*[_process_single_page(idx) for idx in indices_to_process])
    return [d for d in page_results if d is not None]


# ─── Main Extraction Pipeline ───────────────────────────────────────────

async def extract_text_from_file(file_path: str, filename: str) -> list[Document]:
    """
    Enhanced extraction pipeline for PDFs and images.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        def _read_image():
            with open(file_path, "rb") as f:
                return f.read()
        image_bytes = await asyncio.to_thread(_read_image)
        image_type = await classify_image_type(image_bytes)
        doc = await process_image_path(image_type, image_bytes, source_meta="direct_image")
        if not doc.page_content or len(doc.page_content.strip()) < 20:
            raise PDFExtractionError(
                "This image contains no readable text or clinical content. Please upload a clear medical document or digital PDF."
            )
        return [doc]
        
    # Phase 1: Detect table-heavy pages
    table_pages = await asyncio.to_thread(_detect_table_pages, file_path)
    
    # Phase 2: Extract table pages with Vision AI
    vision_docs: list[Document] = []
    if table_pages:
        vision_docs = await _extract_table_pages_with_vision(file_path, table_pages)
    
    vision_page_numbers = {d.metadata.get("page", -1) for d in vision_docs}
    
    # Phase 3: Standard extraction for non-table pages
    best_docs: list[Document] = []

    pypdf2_docs = await asyncio.to_thread(_extract_with_pypdf2, file_path)
    pymupdf_docs = await _extract_with_pymupdf(file_path)

    for docs in [pypdf2_docs, pymupdf_docs]:
        if _char_count(docs) > _char_count(best_docs):
            best_docs = docs

    # Compute candidate character count before running expensive OCR
    candidate_non_vision_docs = (
        [d for d in best_docs if d.metadata.get("page", -1) not in vision_page_numbers]
        if vision_page_numbers
        else best_docs
    )
    total_candidate_chars = _char_count(vision_docs) + _char_count(candidate_non_vision_docs)

    # True fallback: Only invoke Tesseract OCR if native extractors + vision yield insufficient text
    if total_candidate_chars < MIN_EXTRACTED_CHARS:
        logger.info(
            "Native PDF extraction yielded %d chars (< %d threshold); attempting OCR fallback for %s",
            total_candidate_chars,
            MIN_EXTRACTED_CHARS,
            file_path,
        )
        ocr_docs = await asyncio.to_thread(_extract_with_ocr, file_path)
        if _char_count(ocr_docs) > _char_count(best_docs):
            best_docs = ocr_docs

    # Filter out pages already handled by Vision
    if vision_page_numbers:
        best_docs = [d for d in best_docs if d.metadata.get("page", -1) not in vision_page_numbers]
    
    # Phase 4: Merge vision-extracted + standard-extracted docs (filtering empty chunks)
    all_docs = [d for d in vision_docs + best_docs if d.page_content and d.page_content.strip()]
    # Sort by page number for consistent ordering
    all_docs.sort(key=lambda d: d.metadata.get("page", 0))

    if not all_docs or _char_count(all_docs) < 20:
        raise PDFExtractionError(
            "This PDF contains no readable text (it may be a scanned image or empty). Please upload a digital text PDF."
        )

    if _char_count(all_docs) < MIN_EXTRACTED_CHARS:
        raise PDFExtractionError(
            "Could not extract enough readable text from this PDF report. "
            "The file may be scanned, encrypted, or low quality. "
            "Try a text-based PDF or ensure Tesseract OCR is installed on the server."
        )

    return all_docs
