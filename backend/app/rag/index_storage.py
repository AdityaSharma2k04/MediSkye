import os
import re
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


def _extract_index_folder_name(file_path: str | Path) -> str:
    """
    Cross-platform extraction of the terminal folder name from a file_path string.
    Handles both Windows backslashes (\\) and POSIX forward slashes (/) on any OS.
    E.g. 'C:\\Users\\Lenovo\\...\\user_X_doc_Y.index' -> 'user_X_doc_Y.index'
    """
    raw = str(file_path).rstrip("/\\")
    parts = [p for p in re.split(r"[/\\]+", raw) if p]
    return parts[-1] if parts else "unknown.index"


def _resolve_local_index_dir(file_path: str | Path) -> Path:
    """
    Resolve local directory path for an index file_path.
    If the path already exists locally or its parent exists locally, returns it.
    Otherwise resolves inside current OS's settings.INDEX_STORAGE_DIR using the folder name.
    """
    try:
        p = Path(file_path)
        if p.is_absolute() and (p.exists() or p.parent.exists()):
            if os.name == 'nt' or not (len(str(p)) > 1 and str(p)[1] == ':'):
                return p
    except Exception:
        pass
    folder_name = _extract_index_folder_name(file_path)
    base_dir = settings.INDEX_STORAGE_DIR
    return base_dir / folder_name


def get_bm25_path(index_path: str | Path) -> Path:
    """
    Return local path for the corresponding BM25 index JSON file (or legacy pickle if present).
    Cross-platform safe for Windows and Linux paths.
    """
    folder_name = _extract_index_folder_name(index_path)
    stem = folder_name.removesuffix(".index")
    try:
        p = Path(index_path)
        if p.is_absolute() and (p.exists() or p.parent.exists()):
            if os.name == 'nt' or not (len(str(p)) > 1 and str(p)[1] == ':'):
                json_p = p.parent / f"{stem}_bm25.json"
                if json_p.exists():
                    return json_p
                pkl_p = p.parent / f"{stem}_bm25.pkl"
                if pkl_p.exists():
                    return pkl_p
                return json_p
    except Exception:
        pass
    target_dir = _resolve_local_index_dir(index_path)
    json_target = target_dir.parent / f"{stem}_bm25.json"
    if json_target.exists():
        return json_target
    pkl_target = target_dir.parent / f"{stem}_bm25.pkl"
    if pkl_target.exists():
        return pkl_target
    return json_target


def save_index_artifacts(file_path: str | Path, raise_on_error: bool = False) -> bool:
    """
    Sync local FAISS and BM25 index artifacts to Google Cloud Storage (GCS).
    If GCS_INDEX_BUCKET is not configured, no remote sync is performed.
    """
    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        logger.debug("GCS_INDEX_BUCKET not set; skipping GCS upload for %s", file_path)
        return True

    local_path = _resolve_local_index_dir(file_path)
    folder_name = _extract_index_folder_name(file_path)
    stem = folder_name.removesuffix(".index")

    if not local_path.exists():
        logger.warning("Local index directory %s does not exist; cannot upload to GCS", local_path)
        if raise_on_error:
            raise FileNotFoundError(f"Local index directory {local_path} does not exist")
        return False

    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)

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

        # 2. Upload corresponding BM25 file (.json or .pkl)
        bm25_file = get_bm25_path(local_path)
        if bm25_file.exists():
            ext = bm25_file.suffix
            bm25_blob_name = f"indexes/{stem}_bm25{ext}"
            blob = bucket.blob(bm25_blob_name)
            blob.upload_from_filename(str(bm25_file))
            logger.debug("Uploaded BM25 file %s to gs://%s/%s", bm25_file.name, bucket_name, bm25_blob_name)

        logger.info("Successfully persisted index artifacts to gs://%s for %s", bucket_name, folder_name)
        return True
    except Exception as exc:
        logger.error("Failed to upload index artifacts to GCS: %s", exc, exc_info=True)
        if raise_on_error:
            raise
        return False


async def asave_index_artifacts(file_path: str | Path, raise_on_error: bool = False) -> bool:
    """Asynchronously sync local index artifacts to GCS."""
    return await asyncio.to_thread(save_index_artifacts, file_path, raise_on_error)


async def asave_index_artifacts_with_retry(
    file_path: str | Path,
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    max_retries: Optional[int] = None,
) -> bool:
    """
    Asynchronously upload index artifacts to GCS with exponential backoff retry.
    Returns True on success (or if GCS is not enabled), False if all attempts fail.
    """
    if max_retries is not None:
        max_attempts = max_retries
    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        return True

    delay = initial_delay
    for attempt in range(1, max_attempts + 1):
        try:
            await asave_index_artifacts(file_path, raise_on_error=True)
            return True
        except Exception as exc:
            logger.warning(
                "GCS index sync attempt %d/%d failed for %s: %s",
                attempt,
                max_attempts,
                file_path,
                exc,
            )
            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay *= 2
    return False


def ensure_index_local(file_path: str | Path) -> Path:
    """
    Ensure the FAISS and BM25 artifacts for file_path are present on local disk.
    Fast-path: If local file exists, returns immediately (cache hit).
    If missing and GCS_INDEX_BUCKET is configured, downloads artifacts from GCS.
    """
    target_path = _resolve_local_index_dir(file_path)
    folder_name = _extract_index_folder_name(file_path)
    stem = folder_name.removesuffix(".index")

    # Fast cache hit
    if target_path.exists():
        if target_path.is_dir() and (target_path / "index.faiss").exists():
            return target_path
        elif target_path.is_file():
            return target_path

    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        return target_path

    logger.info("Local index cache miss for %s; fetching from gs://%s...", folder_name, bucket_name)
    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
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

        # Download BM25 index (.json preferred, .pkl legacy fallback)
        bm25_blob_json = bucket.blob(f"indexes/{stem}_bm25.json")
        if bm25_blob_json.exists():
            bm25_file = target_path.parent / f"{stem}_bm25.json"
            bm25_file.parent.mkdir(parents=True, exist_ok=True)
            bm25_blob_json.download_to_filename(str(bm25_file))
            logger.debug("Downloaded BM25 JSON from gs://%s/indexes/%s_bm25.json", bucket_name, stem)
        else:
            bm25_blob_pkl = bucket.blob(f"indexes/{stem}_bm25.pkl")
            if bm25_blob_pkl.exists():
                bm25_file = target_path.parent / f"{stem}_bm25.pkl"
                bm25_file.parent.mkdir(parents=True, exist_ok=True)
                bm25_blob_pkl.download_to_filename(str(bm25_file))
                logger.debug("Downloaded legacy BM25 pkl from gs://%s/indexes/%s_bm25.pkl", bucket_name, stem)

        if (target_path / "index.faiss").exists():
            logger.info("Successfully fetched index artifacts from GCS into %s", target_path)
        else:
            logger.warning("Downloaded blobs from GCS prefix %s but index.faiss not found in %s", prefix, target_path)
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

    target_path = _resolve_local_index_dir(file_path)
    folder_name = _extract_index_folder_name(file_path)
    stem = folder_name.removesuffix(".index")
    bm25_file = get_bm25_path(target_path)

    # 1. Local disk deletion
    try:
        if target_path.exists():
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
    except Exception as e:
        logger.warning("Could not delete local FAISS directory %s: %s", target_path, e)

    for ext in (".json", ".pkl"):
        f_bm25 = target_path.parent / f"{stem}_bm25{ext}"
        try:
            if f_bm25.exists():
                os.remove(f_bm25)
        except Exception as e:
            logger.warning("Could not delete local BM25 file %s: %s", f_bm25, e)

    # 2. Remote GCS deletion
    bucket_name = settings.GCS_INDEX_BUCKET
    if not bucket_name:
        return

    try:
        client = _get_storage_client()
        bucket = client.bucket(bucket_name)
        prefix = f"indexes/{folder_name}/"

        for blob in bucket.list_blobs(prefix=prefix):
            blob.delete()

        for ext in (".json", ".pkl"):
            bm25_blob = bucket.blob(f"indexes/{stem}_bm25{ext}")
            if bm25_blob.exists():
                bm25_blob.delete()

        logger.info("Deleted remote index artifacts from gs://%s for %s", bucket_name, folder_name)
    except Exception as exc:
        logger.error("Failed to delete remote index artifacts from GCS: %s", exc, exc_info=True)


async def adelete_index_artifacts(file_path: str | Path) -> None:
    """Asynchronously delete index artifacts from disk and GCS."""
    await asyncio.to_thread(delete_index_artifacts, file_path)
