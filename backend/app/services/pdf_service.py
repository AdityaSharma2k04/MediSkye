import io

import pymupdf as fitz  # PyMuPDF (package renamed from 'fitz')
from app.core.config import settings
from fastapi import HTTPException, status
from PIL import Image

PDF_MAGIC = b"%PDF"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
MAX_IMAGE_PIXELS = 40_000_000
MAX_PAGE_AREA = 2_000_000  # pt^2


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

    # 3. PDF Validation
    if ext_with_dot == ".pdf":
        if not content.startswith(PDF_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header invalid. Must be a valid PDF document.",
            )

        doc = None
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

            for page in doc:
                if page.rect.width * page.rect.height > MAX_PAGE_AREA:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="PDF page dimensions exceed maximum allowed area (2,000,000 pt²).",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Corrupted or unreadable PDF document format.",
            ) from exc
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    # 4. Image Validation (.png, .jpg, .jpeg, .webp)
    if ext_with_dot in [".png", ".jpg", ".jpeg", ".webp"]:
        if ext_with_dot == ".png" and not content.startswith(PNG_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header invalid. Must be a valid PNG image.",
            )
        if ext_with_dot in [".jpg", ".jpeg"] and not content.startswith(JPEG_MAGIC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header invalid. Must be a valid JPEG image.",
            )
        if ext_with_dot == ".webp" and not (content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content header invalid. Must be a valid WebP image.",
            )

        try:
            im = Image.open(io.BytesIO(content))
            im.verify()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Corrupted or unreadable image format.",
            ) from exc

        try:
            im2 = Image.open(io.BytesIO(content))
            if im2.width * im2.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Image dimensions ({im2.width}x{im2.height}) exceed maximum allowed pixels (40 MP).",
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Corrupted or unreadable image format.",
            ) from exc
