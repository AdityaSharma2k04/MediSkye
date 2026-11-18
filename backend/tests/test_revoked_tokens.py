import pytest
import uuid
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException
from sqlalchemy.future import select

from app.core.auth import (
    TOKEN_CACHE_TTL_SECONDS,
    create_access_token,
    _resolve_user_full,
    get_password_hash,
)
from app.db.database import AsyncSessionLocal
from app.db.models import User, RevokedToken
from app.api.v1.endpoints.query import _acquire_chat_advisory_lock


def test_token_cache_ttl_is_ten_seconds():
    assert TOKEN_CACHE_TTL_SECONDS == 10.0


@pytest.mark.asyncio
async def test_revoked_tokens_db_persistence_and_rejection():
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"revoketest_{uuid.uuid4().hex[:8]}@mediskye.com",
            hashed_password=get_password_hash("StrongPass123!"),
            full_name="Revoke Tester",
            phi_consent_granted=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token = create_access_token(data={"sub": user.email})
        import jwt
        from app.core.auth import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload["jti"]
        exp = payload["exp"]

        # 1. Before revocation, user resolves cleanly
        resolved_user = await _resolve_user_full(token, db)
        assert resolved_user is not None
        assert resolved_user.id == user.id

        # 2. Add token to RevokedToken table
        revoked_row = RevokedToken(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.fromtimestamp(exp, tz=UTC),
        )
        db.add(revoked_row)
        await db.commit()

        # 3. Query RevokedToken directly
        found = await db.scalar(select(RevokedToken.jti).where(RevokedToken.jti == jti))
        assert found == jti

        # 4. Attempting to resolve token must raise 401 "Token has been revoked"
        with pytest.raises(HTTPException) as exc_info:
            await _resolve_user_full(token, db)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_acquire_chat_advisory_lock_safe_on_non_postgresql():
    async with AsyncSessionLocal() as db:
        # On SQLite / test database, advisory lock helper returns True without crashing
        result = await _acquire_chat_advisory_lock(db, f"test_session_{uuid.uuid4().hex}")
        assert result is True
