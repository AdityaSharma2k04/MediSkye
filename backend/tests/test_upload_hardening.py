import io
import uuid
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from PIL import Image

from app.core.config import settings
from app.services.pdf_service import validate_file_upload
from app.core.redis_client import MockRedis
from app.db.models import User, Document
from app.db.database import AsyncSessionLocal
from app.core.auth import get_password_hash

TEST_PASSWORD = "ValidPass123!@#"


def test_image_validation_rejects_invalid_magic_bytes():
    """Verify PNG/JPEG uploads without valid magic bytes are rejected with HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(b"NOT_A_PNG_HEADER_DATA", filename="lab_scan.png")
    assert exc_info.value.status_code == 400
    assert "Must be a valid PNG image" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(b"NOT_A_JPEG_HEADER_DATA", filename="lab_scan.jpg")
    assert exc_info.value.status_code == 400
    assert "Must be a valid JPEG image" in exc_info.value.detail


def test_image_validation_rejects_corrupted_image_format():
    """Verify PNG with valid magic bytes but corrupted stream is rejected with HTTP 422."""
    corrupted_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(corrupted_png, filename="lab_scan.png")
    assert exc_info.value.status_code == 422
    assert "Corrupted or unreadable image format" in exc_info.value.detail


def test_image_validation_rejects_oversized_pixel_dimensions():
    """Verify image exceeding MAX_IMAGE_PIXELS (40MP) is rejected with HTTP 422."""
    # Create a small valid PNG in memory
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()

    # Mock Image.open on the second call (im2) to return oversized dimensions
    mock_img = MagicMock()
    mock_img.width = 7000
    mock_img.height = 6000  # 42,000,000 pixels > 40MP

    with patch("app.services.pdf_service.Image.open") as mock_open:
        mock_open.side_effect = [Image.open(io.BytesIO(valid_png_bytes)), mock_img]
        with pytest.raises(HTTPException) as exc_info:
            validate_file_upload(valid_png_bytes, filename="giant_scan.png")
        assert exc_info.value.status_code == 422
        assert "exceed maximum allowed pixels" in exc_info.value.detail


def test_image_validation_accepts_valid_jpeg_and_webp():
    """Verify valid JPEG and WebP image formats pass validation without errors."""
    img = Image.new("RGB", (100, 100), color="blue")
    buf_jpg = io.BytesIO()
    img.save(buf_jpg, format="JPEG")
    valid_jpg_bytes = buf_jpg.getvalue()
    res_jpg = validate_file_upload(valid_jpg_bytes, filename="lab_camera_shot.jpg")
    assert res_jpg is None

    buf_webp = io.BytesIO()
    img.save(buf_webp, format="WEBP")
    valid_webp_bytes = buf_webp.getvalue()
    res_webp = validate_file_upload(valid_webp_bytes, filename="lab_camera_shot.webp")
    assert res_webp is None


@pytest.mark.asyncio
async def test_mock_redis_ttl_expiry_and_eviction():
    """Verify MockRedis monotonic TTL expiry and eviction."""
    redis = MockRedis()
    await redis.setex("key1", 1, "value1")
    assert await redis.get("key1") == "value1"

    # Simulate passage of time past TTL
    redis.expiry["key1"] = time.monotonic() - 1.0
    assert await redis.get("key1") is None
    assert "key1" not in redis.store


@pytest.mark.asyncio
async def test_failed_document_status_raises_422():
    """Verify that querying or fetching metrics for a document marked failed returns 422."""
    from app.api.v1.endpoints.metrics import _get_or_extract_metrics
    from app.core.auth import UserDTO

    test_user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        u = User(
            id=test_user_id,
            email=f"failed_doc_user_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(u)
        doc = Document(
            id=doc_id,
            user_id=test_user_id,
            filename="failed_scan.pdf",
            title="Failed Scan",
            index_status="failed",
        )
        session.add(doc)
        await session.commit()

    user_dto = UserDTO(
        id=test_user_id,
        email="test@example.com",
        phi_consent_granted=True,
        memory_consent_granted=True,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await _get_or_extract_metrics(
                doc_id=doc_id,
                force_refresh=False,
                current_user=user_dto,
                db=session,
            )
        assert exc_info.value.status_code == 422
        assert "could not be processed" in exc_info.value.detail
