import os
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


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    # Remove null bytes and non-printable control characters (except newline, tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normalize multiple whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def escape_xml_content(text: str) -> str:
    """Escape XML-significant characters in untrusted content before prompt interpolation.

    Prevents prompt injection via XML tag breakout (e.g., a malicious PDF
    containing '</excerpt></document><system>...' would otherwise break out
    of the XML encapsulation in the RAG prompt).
    """
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
    )


def sanitize_filename(filename: str, max_len: int = 100) -> str:
    """Sanitize and strip dangerous control characters, XML/HTML tags, path traversal,
    and excessive length from filenames before database storage or prompt interpolation.
    """
    if not filename:
        return "document.pdf"
    # Strip HTML tags first so closing tags (e.g. </script>) do not act as path separators
    base = re.sub(r"<[^>]*>", "", filename.strip())
    # Take basename only to prevent directory traversal
    base = os.path.basename(base.replace("\\", "/"))
    # Remove null bytes and non-printable control characters
    base = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", base)
    # Strip XML/HTML brackets, quotes, and dangerous injection characters
    base = re.sub(r'[<>"\'`;$|&{}]', "", base)
    # Normalize multiple whitespace
    base = re.sub(r"\s+", " ", base).strip()
    name, ext = os.path.splitext(base)
    if not ext:
        ext = ".pdf"
    # Bound max length while preserving extension
    allowed_name_len = max(1, max_len - len(ext))
    name = name[:allowed_name_len].strip()
    clean_name = f"{name}{ext}".strip()
    return clean_name if clean_name and clean_name != ext else f"document{ext}"


def clean_filename_to_title(filename: str) -> str:
    """Derive a clean, readable human title from an uploaded file name."""
    if not filename:
        return "New Conversation"
    # Strip extension (e.g. .pdf, .png, .jpg, .jpeg)
    raw_name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
    name = re.sub(r"[_-]+", " ", raw_name)
    # Remove common noise words (case-insensitive)
    noise_pattern = r"\b(report|final|v\d+|rev|draft|scan|result|results|lab|blood|test|copy|sample|patient)\b"
    cleaned = re.sub(noise_pattern, "", name, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b\d{4,}\b", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if not cleaned:
        cleaned = re.sub(r"\s{2,}", " ", name).strip()
    # Title-case each word
    title = " ".join(w.capitalize() for w in cleaned.split())
    # Limit to 40 chars, truncate at word boundary
    if len(title) > 40:
        truncated = title[:40].rsplit(" ", 1)[0]
        title = truncated if truncated else title[:40]
    return title or "New Conversation"


def safe_language(value: Optional[str], default: str = "English") -> str:
    """Allow only alphabetic characters, spaces, hyphens, and parentheses up to 40 chars."""
    if not value or not isinstance(value, str):
        return default
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 40:
        return default
    if not re.match(r"^[a-zA-Z\s\-()]+$", cleaned):
        return default
    return cleaned


def generate_title_from_query(query: str, max_words: int = 5, max_len: int = 60) -> str:
    """Generate a clean chat title from the first N words of a user query."""
    if not query:
        return "New Conversation"
    cleaned = sanitize_text(query).strip()
    words = cleaned.split()
    if not words:
        return "New Conversation"
    title = " ".join(words[:max_words])
    if len(title) > max_len:
        title = title[:max_len].strip()
    return title or "New Conversation"

