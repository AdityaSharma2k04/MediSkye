import pytest
import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

from app.rag.index_storage import (
    ensure_index_local,
    save_index_artifacts,
    delete_index_artifacts,
    get_bm25_path,
)
from app.services.upload_jobs import create_job, cleanup_stale_jobs, get_job, clear_jobs
from app.db.database import AsyncSessionLocal
from app.db.models import User, UploadJob
from sqlalchemy import select


def test_get_bm25_path():
    path = "/tmp/indexes/user_1_doc_2.index"
    bm25 = get_bm25_path(path)
    assert bm25.name == "user_1_doc_2_bm25.json"


def test_ensure_index_local_cache_hit(tmp_path):
    index_dir = tmp_path / "user_1_doc_2.index"
    index_dir.mkdir()
    (index_dir / "index.faiss").write_text("faiss data")
    (index_dir / "index.pkl").write_text("pkl data")

    with patch("app.rag.index_storage.settings.GCS_INDEX_BUCKET", "test-bucket"), \
         patch("app.rag.index_storage._get_storage_client") as mock_client:
        resolved = ensure_index_local(str(index_dir))
        assert resolved == index_dir
        # Fast cache hit should not touch GCS client
        mock_client.assert_not_called()


def test_ensure_index_local_downloads_from_gcs_on_cache_miss(tmp_path):
    index_dir = tmp_path / "user_missing_doc_9.index"
    bm25_file = tmp_path / "user_missing_doc_9_bm25.pkl"

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    mock_blob_faiss = MagicMock()
    mock_blob_faiss.name = f"indexes/{index_dir.name}/index.faiss"
    mock_blob_pkl = MagicMock()
    mock_blob_pkl.name = f"indexes/{index_dir.name}/index.pkl"

    mock_bucket.list_blobs.return_value = [mock_blob_faiss, mock_blob_pkl]

    with patch("app.rag.index_storage.settings.GCS_INDEX_BUCKET", "test-bucket"), \
         patch("app.rag.index_storage._get_storage_client", return_value=mock_client):
        resolved = ensure_index_local(str(index_dir))
        assert resolved == index_dir
        assert mock_blob_faiss.download_to_filename.call_count == 1
        assert mock_blob_pkl.download_to_filename.call_count == 1


def test_save_index_artifacts_uploads_faiss_and_bm25(tmp_path):
    index_dir = tmp_path / "user_upload_doc_1.index"
    index_dir.mkdir()
    faiss_file = index_dir / "index.faiss"
    faiss_file.write_text("faiss")
    bm25_file = tmp_path / "user_upload_doc_1_bm25.pkl"
    bm25_file.write_text("bm25")

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    with patch("app.rag.index_storage.settings.GCS_INDEX_BUCKET", "test-bucket"), \
         patch("app.rag.index_storage._get_storage_client", return_value=mock_client):
        save_index_artifacts(str(index_dir))
        assert mock_blob.upload_from_filename.call_count >= 2


def test_delete_index_artifacts_removes_local_and_gcs(tmp_path):
    index_dir = tmp_path / "user_del_doc_1.index"
    index_dir.mkdir()
    (index_dir / "index.faiss").write_text("faiss")
    bm25_file = tmp_path / "user_del_doc_1_bm25.pkl"
    bm25_file.write_text("bm25")

    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.list_blobs.return_value = [mock_blob]
    mock_bucket.blob.return_value = mock_blob
    mock_blob.exists.return_value = True

    with patch("app.rag.index_storage.settings.GCS_INDEX_BUCKET", "test-bucket"), \
         patch("app.rag.index_storage._get_storage_client", return_value=mock_client):
        delete_index_artifacts(str(index_dir))
        assert not index_dir.exists()
        assert not bm25_file.exists()
        assert mock_blob.delete.call_count >= 1


@pytest.mark.anyio
async def test_cleanup_stale_jobs():
    await clear_jobs()

    import uuid
    dummy_user_id = uuid.uuid4()

    # Create dummy user first for foreign key constraint
    async with AsyncSessionLocal() as session:
        u = User(id=dummy_user_id, email=f"job_clean_{dummy_user_id}@test.com", hashed_password="pw")
        session.add(u)
        await session.commit()

    # Create fresh job
    fresh_job_id = await create_job(dummy_user_id)

    # Create stale job
    stale_job_id = await create_job(dummy_user_id)
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(UploadJob).filter(UploadJob.id == stale_job_id))
        stale_job = res.scalars().first()
        stale_job.created_at = datetime.now(UTC) - timedelta(hours=30)
        await session.commit()

    deleted_count = await cleanup_stale_jobs(max_age_hours=24)
    assert deleted_count >= 1

    # Fresh job remains, stale job deleted
    assert await get_job(fresh_job_id) is not None
    assert await get_job(stale_job_id) is None
