import pymupdf as fitz  # PyMuPDF (package renamed from 'fitz')
from fastapi import HTTPException, status
from app.core.config import settings

PDF_MAGIC = b"%PDF"


def validate_file_upload(content: bytes, filename: str = "report.pdf") -> None:
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 1. Size Limit Check (50MB)
    max_bytes = settings.MEDISKYE_MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum upload size is {settings.MEDISKYE_MAX_UPLOAD_MB} MB.",
        )

    # 2. Extension Check
    ext = filename.lower().split('.')[-1]
    if ext not in ["pdf", "jpg", "jpeg", "png"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension. Only .pdf, .jpg, .jpeg, and .png files are accepted.",
        )

    # 3. Magic Bytes Check for PDF
    if ext == "pdf" and not content.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content header invalid. Must be a valid PDF document.",
        )

    # 4. Deep Inspection (Page count bomb check & corruption check) for PDF
    if ext == "pdf":
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            if doc.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Uploaded PDF is encrypted or password protected. Please provide an unencrypted PDF.",
                )
                
            page_count = len(doc)
            if page_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PDF report contains no readable pages.",
                )
                
            if page_count > settings.MAX_PDF_PAGES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"PDF report exceeds maximum page limit of {settings.MAX_PDF_PAGES} pages.",
                )
            doc.close()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Corrupted or unreadable PDF document format.",
            ) from exc
