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
    ext_raw = filename.lower().split('.')[-1] if '.' in filename else ''
    ext_with_dot = f".{ext_raw}"
    allowed_exts = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in settings.ALLOWED_EXTENSIONS]
    if ext_with_dot not in allowed_exts:
        ext_list_str = ", ".join(allowed_exts)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension. Only {ext_list_str} files are accepted.",
        )

    # 3. Magic Bytes Check for PDF
    if ext_with_dot == ".pdf" and not content.startswith(PDF_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content header invalid. Must be a valid PDF document.",
        )

    # 4. Deep Inspection (Page count bomb check & corruption check) for PDF
    if ext_with_dot == ".pdf":
        try:
            doc = fitz.open(stream=content, filetype="pdf")
            if doc.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Uploaded PDF is encrypted or password protected. Please provide an unencrypted PDF.",
                )
                
            page_count = len(doc)
            if page_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Corrupted or unreadable PDF document format.",
            ) from exc
