import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_storage_client():
    from google.cloud import storage
    if settings.GOOGLE_GENAI_USE_ENTERPRISE and settings.GOOGLE_CLOUD_PROJECT:
        return storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
    return storage.Client()


def get_bm25_path(index_path: str | Path) -> Path:
    p = Path(index_path)
    return p.parent / f"{p.stem}_bm25.pkl"


def save_index_artifacts(file_path: str | Path) -> None:
    """
    Sync local FAISS and BM25 index artifacts to Google Cloud Storage (GCS).
    If GCS_INDEX_BUCKET is not configured, no remote sync is performed.
    """
    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        logger.debug("GCS_INDEX_BUCKET not set; skipping GCS upload for %s", file_path)
        return

    local_path = Path(file_path)
    if not local_path.exists():
        logger.warning("Local index directory %s does not exist; cannot upload to GCS", file_path)
        return

    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        folder_name = local_path.name

        # 1. Upload FAISS directory files (index.faiss, index.pkl)
        if local_path.is_dir():
            for item in local_path.iterdir():
                if item.is_file():
                    blob_name = f"indexes/{folder_name}/{item.name}"
                    blob = bucket.blob(blob_name)
                    blob.upload_from_filename(str(item))
                    logger.debug("Uploaded FAISS file %s to gs://%s/%s", item.name, bucket_name, blob_name)
        elif local_path.is_file():
            blob_name = f"indexes/{folder_name}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(str(local_path))

        # 2. Upload corresponding BM25 pickle file
        bm25_file = get_bm25_path(local_path)
        if bm25_file.exists():
            bm25_blob_name = f"indexes/{bm25_file.name}"
            blob = bucket.blob(bm25_blob_name)
            blob.upload_from_filename(str(bm25_file))
            logger.debug("Uploaded BM25 file %s to gs://%s/%s", bm25_file.name, bucket_name, bm25_blob_name)

        logger.info("Successfully persisted index artifacts to gs://%s for %s", bucket_name, local_path.name)
    except Exception as exc:
        logger.error("Failed to upload index artifacts to GCS: %s", exc, exc_info=True)


async def asave_index_artifacts(file_path: str | Path) -> None:
    """Asynchronously sync local index artifacts to GCS."""
    await asyncio.to_thread(save_index_artifacts, file_path)


def ensure_index_local(file_path: str | Path) -> Path:
    """
    Ensure the FAISS and BM25 artifacts for file_path are present on local disk.
    Fast-path: If local file exists, returns immediately (cache hit).
    If missing and GCS_INDEX_BUCKET is configured, downloads artifacts from GCS.
    """
    target_path = Path(file_path)

    # Fast cache hit
    if target_path.exists():
        if target_path.is_dir() and (target_path / "index.faiss").exists():
            return target_path
        elif target_path.is_file():
            return target_path

    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        return target_path

    logger.info("Local index cache miss for %s; fetching from gs://%s...", target_path.name, bucket_name)
    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        folder_name = target_path.name
        prefix = f"indexes/{folder_name}/"

        blobs = list(bucket.list_blobs(prefix=prefix))
        if blobs:
            target_path.mkdir(parents=True, exist_ok=True)
            for blob in blobs:
                filename = blob.name.removeprefix(prefix)
                if filename:
                    dest_file = target_path / filename
                    blob.download_to_filename(str(dest_file))
                    logger.debug("Downloaded %s to %s", blob.name, dest_file)

        # Download BM25 pickle
        bm25_file = get_bm25_path(target_path)
        bm25_blob_name = f"indexes/{bm25_file.name}"
        bm25_blob = bucket.blob(bm25_blob_name)
        if bm25_blob.exists():
            bm25_file.parent.mkdir(parents=True, exist_ok=True)
            bm25_blob.download_to_filename(str(bm25_file))
            logger.debug("Downloaded BM25 index from gs://%s/%s", bucket_name, bm25_blob_name)

        logger.info("Successfully fetched index artifacts from GCS into %s", target_path)
    except Exception as exc:
        logger.error("Failed to download index artifacts from GCS: %s", exc, exc_info=True)

    return target_path


async def aensure_index_local(file_path: str | Path) -> Path:
    """Asynchronously ensure index artifacts are cached locally."""
    return await asyncio.to_thread(ensure_index_local, file_path)


def delete_index_artifacts(file_path: str | Path) -> None:
    """
    Delete index artifacts both from local storage, in-memory cache, and from GCS.
    """
    try:
        from app.rag.retriever import evict_index_cache
        evict_index_cache(file_path)
    except Exception as ee:
        logger.debug("Failed to evict index from in-memory cache: %s", ee)

    target_path = Path(file_path)

    # 1. Local disk deletion
    try:
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
    except Exception as e:
        logger.warning("Could not delete local FAISS directory %s: %s", target_path, e)

    bm25_file = get_bm25_path(target_path)
    try:
        if bm25_file.exists():
            os.remove(bm25_file)
    except Exception as e:
        logger.warning("Could not delete local BM25 file %s: %s", bm25_file, e)

    # 2. Remote GCS deletion
    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        return

    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        folder_name = target_path.name
        prefix = f"indexes/{folder_name}/"

        for blob in bucket.list_blobs(prefix=prefix):
            blob.delete()

        bm25_blob = bucket.blob(f"indexes/{bm25_file.name}")
        if bm25_blob.exists():
            bm25_blob.delete()

        logger.info("Deleted remote index artifacts from gs://%s for %s", bucket_name, folder_name)
    except Exception as exc:
        logger.error("Failed to delete remote index artifacts from GCS: %s", exc, exc_info=True)


async def adelete_index_artifacts(file_path: str | Path) -> None:
    """Asynchronously delete index artifacts from disk and GCS."""
    await asyncio.to_thread(delete_index_artifacts, file_path)
