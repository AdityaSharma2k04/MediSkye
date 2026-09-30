import re
import uuid
import secrets
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings


def verify_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.MEDISKYE_API_KEY:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.MEDISKYE_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API authorization key.",
        )


def validate_session_id(session_id: str) -> str:
    try:
        return str(uuid.UUID(session_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id. Must be a valid UUID string.",
        ) from exc


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    # Remove null bytes and non-printable control characters (except newline, tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normalize multiple whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()
