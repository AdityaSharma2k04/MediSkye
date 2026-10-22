import uuid
import time
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select
from sqlalchemy.exc import InvalidRequestError

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User, Document, Chat
from app.core.auth import (
    create_access_token,
    get_password_hash,
    get_cached_user_dto,
    cache_user_dto,
    evict_token_cache_for_user,
    UserDTO,
    get_current_user_full,
    get_current_user,
)
from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_503_before_side_effects_on_index_miss():
    """
    Mandatory Test 1: Simulate index miss.
    Assert 503/425 returned with Retry-After: 2.
    Assert NO Message/Chat row created in DB.
    Assert NO Gemini LLM call made.
    """
    user_email = f"sre_miss_{uuid.uuid4().hex[:8]}@example.com"
    doc_id = uuid.uuid4()
    session_id = str(uuid.uuid4())
    non_existent_path = f"uploads/{user_email}/nonexistent_index_{doc_id}"

    async with AsyncSessionLocal() as session:
        user = User(
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            id=doc_id,
            user_id=user.id,
            filename="missing_lab.pdf",
            file_path=non_existent_path,
            index_status="local_ready",  # Marked ready in DB but files missing everywhere
        )
        session.add(doc)
        await session.commit()

        # Count chat rows before
        chats_before_res = await session.execute(select(Chat).filter(Chat.user_id == user.id))
        chats_before = len(chats_before_res.scalars().all())

    token = create_access_token(data={"sub": user_email})
    headers = {"Authorization": f"Bearer {token}"}

    mock_client = MagicMock()
    mock_gemini_stream = MagicMock()
    mock_gemini_generate = MagicMock()
    mock_client.models.generate_content_stream = mock_gemini_stream
    mock_client.models.generate_content = mock_gemini_generate

    with (
        patch("app.rag.index_storage.aensure_index_local", new_callable=AsyncMock, return_value=Path(non_existent_path)),
        patch("google.genai.Client", return_value=mock_client),
        patch("app.llm.gemini_client.get_genai_client", return_value=mock_client),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/query",
                json={
                    "session_id": session_id,
                    "query": "What are my platelets?",
                    "document_id": str(doc_id),
                },
                headers=headers,
            )

        assert res.status_code in (425, 503), f"Expected 425/503 on index miss, got {res.status_code}: {res.text}"
        assert res.headers.get("retry-after") == "2" or res.headers.get("Retry-After") == "2"

    # Verify zero Chat rows were inserted into DB
    async with AsyncSessionLocal() as session:
        chats_after_res = await session.execute(select(Chat).filter(Chat.user_id == user.id))
        chats_after = len(chats_after_res.scalars().all())
        assert chats_after == chats_before, "Side effect detected! Chat/Message row was created despite index miss."

    # Verify zero Gemini calls were made
    assert mock_gemini_stream.call_count == 0, "Side effect detected! Gemini stream was called on missing index."
    assert mock_gemini_generate.call_count == 0, "Side effect detected! Gemini content was called on missing index."


@pytest.mark.asyncio
async def test_building_state_returns_503():
    """
    Mandatory Test 2: Request during index_status == 'building'.
    Assert 503/425 returned with Retry-After: 2 before any processing.
    """
    user_email = f"sre_building_{uuid.uuid4().hex[:8]}@example.com"
    doc_id = uuid.uuid4()
    session_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        user = User(
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        doc = Document(
            id=doc_id,
            user_id=user.id,
            filename="building_report.pdf",
            file_path=f"uploads/{user_email}/building_{doc_id}",
            index_status="building",  # Currently building
        )
        session.add(doc)
        await session.commit()

    token = create_access_token(data={"sub": user_email})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(
            "/query",
            json={
                "session_id": session_id,
                "query": "Tell me about my test",
                "document_id": str(doc_id),
            },
            headers=headers,
        )

    assert res.status_code in (425, 503), f"Expected 425/503 during building status, got {res.status_code}: {res.text}"
    assert res.headers.get("retry-after") == "2" or res.headers.get("Retry-After") == "2"
    assert "building" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_gcs_retry_backoff_success(tmp_path):
    """
    Mandatory Test 3: GCS Retry Backoff.
    Simulate 2 failed GCS upload attempts -> 3rd succeeds -> index_status == 'synced'.
    """
    from app.rag.index_storage import asave_index_artifacts_with_retry

    # Create dummy index files in local tmp_path
    local_dir = tmp_path / "dummy_index"
    local_dir.mkdir(parents=True, exist_ok=True)
    (local_dir / "index.faiss").write_bytes(b"FAISS_DUMMY_DATA")
    (local_dir / "index.pkl").write_bytes(b"PKL_DUMMY_DATA")

    attempts = 0

    def mock_upload(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError(f"Transient GCS 503 error attempt {attempts}")
        return True

    mock_blob = MagicMock()
    mock_blob.upload_from_filename.side_effect = mock_upload

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    mock_storage_client = MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket

    with (
        patch("google.cloud.storage.Client", return_value=mock_storage_client),
        patch("app.rag.index_storage.settings.GCS_INDEX_BUCKET", "test-bucket"),
    ):
        result = await asave_index_artifacts_with_retry(str(local_dir), max_retries=3, initial_delay=0.01)
        assert result is True, "asave_index_artifacts_with_retry should succeed on 3rd attempt"
        assert attempts >= 3, f"Expected at least 3 attempts, got {attempts}"


@pytest.mark.asyncio
async def test_deferred_phi_guard_raises_on_lazy_access():
    """
    Mandatory Test 4: Deferred-PHI Guard.
    Accessing health_profile on User without get_current_user_full raises InvalidRequestError.
    Accessing health_profile on UserDTO raises InvalidRequestError.
    """
    # 1. On un-hydrated User ORM object
    raw_user = User(
        id=uuid.uuid4(),
        email="phi_guard@test.com",
        blood_type="O+",
    )
    with pytest.raises(InvalidRequestError) as exc_info:
        _ = raw_user.health_profile
    assert "lazy='raise'" in str(exc_info.value)
    assert "get_current_user_full" in str(exc_info.value)

    # 2. On UserDTO
    dto = UserDTO(
        id=raw_user.id,
        email=raw_user.email,
        phi_consent_granted=True,
    )
    with pytest.raises(InvalidRequestError) as exc_info_dto:
        _ = dto.health_profile
    assert "lazy='raise'" in str(exc_info_dto.value)

    # 3. When loaded via get_current_user_full, _phi_loaded=True allows health_profile access
    raw_user._phi_loaded = True
    profile = raw_user.health_profile
    assert isinstance(profile, dict)
    assert profile["blood_type"] == "O+"


@pytest.mark.asyncio
async def test_auth_cache_invalidation_on_profile_update_and_delete():
    """
    Mandatory Test 5: Auth Cache Invalidation.
    Verify cached token is evicted on PUT/PATCH /users/me and DELETE /users/me.
    """
    user_email = f"auth_cache_{uuid.uuid4().hex[:8]}@example.com"
    token = create_access_token(data={"sub": user_email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncSessionLocal() as session:
        user = User(
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            full_name="Original Name",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Pre-seed cache by calling an endpoint using get_current_user
        chats_res = await ac.get("/users/me/chats", headers=headers)
        assert chats_res.status_code == 200

        # Assert token is now in cache
        cached = get_cached_user_dto(token)
        assert cached is not None, "Token should be present in memory cache after request"
        assert str(cached.id) == str(user_id)

        # 1. Update profile via PATCH /users/me -> evicts token cache
        patch_res = await ac.patch(
            "/users/me",
            json={"full_name": "Updated Staff SRE"},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["full_name"] == "Updated Staff SRE"

        # Assert cache was evicted
        assert get_cached_user_dto(token) is None, "Cache was not evicted on PATCH /users/me"

        # Pre-seed cache again
        await ac.get("/users/me/chats", headers=headers)
        assert get_cached_user_dto(token) is not None, "Cache should be re-populated"

        # 2. Delete user via DELETE /users/me -> evicts token cache
        del_res = await ac.delete("/users/me", headers=headers)
        assert del_res.status_code == 204

        # Assert cache was evicted
        assert get_cached_user_dto(token) is None, "Cache was not evicted on DELETE /users/me"


def test_unique_index_migration_autocommit():
    """
    Mandatory Test 6: Unique Index Migration.
    Verifies the Alembic migration uses transactional CREATE UNIQUE INDEX IF NOT EXISTS for LOWER(email).
    """
    from pathlib import Path
    migrations_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    migration_files = list(migrations_dir.glob("*_add_lower_email_unique_index_and_index_status.py"))
    assert len(migration_files) == 1, "Expected migration file not found in alembic/versions"

    content = migration_files[0].read_text()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_lower_email" in content
    assert "index_status" in content
    assert "CONCURRENTLY" not in content
    assert "AUTOCOMMIT" not in content



@pytest.mark.asyncio
async def test_delete_account_invalidates_firebase_token():
    """
    Verify DELETE /users/me resolves and deletes Firebase user by email,
    evicts cache, and subsequent requests with the token return 401.
    """
    import firebase_admin.auth

    user_email = f"fb_del_{uuid.uuid4().hex[:8]}@example.com"
    fake_token = f"fake_fb_token_{uuid.uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {fake_token}"}

    # Create user in DB
    async with AsyncSessionLocal() as session:
        user = User(
            email=user_email,
            hashed_password=get_password_hash(TEST_PASSWORD),
            phi_consent_granted=True,
            full_name="Firebase Deletion Test User",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    mock_fb_user = MagicMock()
    mock_fb_user.uid = "test-uid-123"

    mock_get_user = MagicMock(return_value=mock_fb_user)
    mock_del_user = MagicMock(return_value=None)
    mock_verify_token = MagicMock(return_value={"uid": "test-uid-123", "email": user_email, "name": "Firebase Deletion Test User"})

    transport = ASGITransport(app=app)
    with patch("firebase_admin.auth.get_user_by_email", mock_get_user), \
         patch("firebase_admin.auth.delete_user", mock_del_user), \
         patch("firebase_admin.auth.verify_id_token", mock_verify_token):

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Pre-seed authentication & cache
            get_res_before = await ac.get("/users/me", headers=headers)
            assert get_res_before.status_code == 200

            # 2. Call DELETE /users/me
            del_res = await ac.delete("/users/me", headers=headers)
            assert del_res.status_code == 204

            # 3. Assertions on get_user_by_email and delete_user
            mock_get_user.assert_called_once_with(user_email)
            mock_del_user.assert_called_once_with("test-uid-123")

            # 4. Simulate post-deletion state where Firebase token verification fails
            mock_verify_token.side_effect = firebase_admin.auth.UserNotFoundError("User was deleted")

            # 5. Subsequent request with the same token must return 401
            get_res_after = await ac.get("/users/me", headers=headers)
            assert get_res_after.status_code == 401

