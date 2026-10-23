import uuid
import asyncio
import secrets
import logging
import hashlib
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
import threading
from datetime import datetime, timedelta, UTC
from typing import Optional, Any
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, Field
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from app.core.redis_client import redis_client

# JWT Settings
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # TODO: implement refresh tokens (Phase 3) for longer sessions

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


class UserDTO(BaseModel):
    """
    Lightweight Pydantic DTO returned on the high-throughput auth hot path.
    Prevents unnecessary ORM queries and lazy loading in async SQLAlchemy.
    PHI fields are marked exclude=True so generic model_dump() calls never leak PHI.
    """
    id: uuid.UUID
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    email_verified: bool = True
    language_preference: Optional[str] = "English"
    phi_consent_granted: bool = False
    memory_consent_granted: bool = False
    full_name: Optional[str] = None
    date_of_birth: Optional[Any] = None
    biological_sex: Optional[str] = None
    blood_type: Optional[str] = Field(default=None, exclude=True)
    pre_existing_conditions: Optional[str] = Field(default=None, exclude=True)
    known_allergies: Optional[str] = Field(default=None, exclude=True)
    current_medications: Optional[str] = Field(default=None, exclude=True)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    height_cm: Optional[float] = None
    diet_type: Optional[str] = None
    activity_level: Optional[str] = None
    occupation: Optional[str] = Field(default=None, exclude=True)

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    @property
    def health_profile(self):
        raise InvalidRequestError("'User.health_profile' is set to lazy='raise', unable to load attribute for instance. Use get_current_user_full.")


# In-Memory Token Hash TTL Cache (60s TTL, maxsize=1024)
_TOKEN_CACHE_LOCK = threading.Lock()
_TOKEN_CACHE: OrderedDict[str, dict] = OrderedDict()
TOKEN_CACHE_TTL_SECONDS = 60.0
TOKEN_CACHE_MAX_SIZE = 1024


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_cached_user_dto(token: str) -> Optional[UserDTO]:
    key = _hash_token(token)
    now = time.time()
    with _TOKEN_CACHE_LOCK:
        entry = _TOKEN_CACHE.get(key)
        if not entry:
            return None
        dto = entry.get("dto")
        if entry["expires_at"] <= now or not getattr(dto, "email_verified", True):
            _TOKEN_CACHE.pop(key, None)
            return None
        _TOKEN_CACHE.move_to_end(key)
        return dto


def cache_user_dto(token: str, dto: UserDTO) -> None:
    # Never cache unverified tokens so a 403 rejection can never poison the 60s cache.
    if not getattr(dto, "email_verified", True):
        return
    key = _hash_token(token)
    expires_at = time.time() + TOKEN_CACHE_TTL_SECONDS
    with _TOKEN_CACHE_LOCK:
        if len(_TOKEN_CACHE) >= TOKEN_CACHE_MAX_SIZE:
            _TOKEN_CACHE.popitem(last=False)
        _TOKEN_CACHE[key] = {
            "dto": dto,
            "user_id": str(dto.id),
            "expires_at": expires_at,
        }


def evict_token_cache_for_user(user_id: Any) -> int:
    """Explicitly evict cached tokens for a user_id."""
    uid_str = str(user_id)
    with _TOKEN_CACHE_LOCK:
        keys_to_evict = [k for k, v in _TOKEN_CACHE.items() if v.get("user_id") == uid_str]
        for k in keys_to_evict:
            _TOKEN_CACHE.pop(k, None)
    return len(keys_to_evict)


def evict_token_cache_by_token(token: str) -> None:
    key = _hash_token(token)
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE.pop(key, None)


def clear_token_cache() -> None:
    """Clear all entries in token cache (useful for test resets)."""
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE.clear()


# Single-flight guard: the SPA fires GET /users/me and GET /users/me/dependents
# in parallel right after login. Without coalescing, BOTH miss the empty cache
# and each pays the full Firebase verification (incl. the check_revoked RPC).
# Concurrent misses for the same token now wait for one resolution and then
# read the freshly populated cache.
_INFLIGHT_RESOLUTIONS: dict = {}


@asynccontextmanager
async def _single_flight(key: str):
    slot = _INFLIGHT_RESOLUTIONS.get(key)
    if slot is None:
        slot = [asyncio.Lock(), 0]
        _INFLIGHT_RESOLUTIONS[key] = slot
    slot[1] += 1
    try:
        async with slot[0]:
            yield
    finally:
        slot[1] -= 1
        if slot[1] == 0 and _INFLIGHT_RESOLUTIONS.get(key) is slot:
            _INFLIGHT_RESOLUTIONS.pop(key, None)


def _short_hash(token: str) -> str:
    return _hash_token(token)[:12]


def _user_to_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        email=user.email,
        created_at=user.created_at or datetime.now(UTC),
        email_verified=True,
        language_preference=user.language_preference,
        phi_consent_granted=bool(user.phi_consent_granted),
        memory_consent_granted=bool(user.memory_consent_granted),
        full_name=user.full_name,
        date_of_birth=user.date_of_birth,
        biological_sex=user.biological_sex,
        blood_type=user.blood_type,
        pre_existing_conditions=user.pre_existing_conditions,
        known_allergies=user.known_allergies,
        current_medications=user.current_medications,
        emergency_contact_name=user.emergency_contact_name,
        emergency_contact_phone=user.emergency_contact_phone,
        height_cm=user.height_cm,
        diet_type=user.diet_type,
        activity_level=user.activity_level,
        occupation=user.occupation,
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_bytes = plain_password.encode("utf-8")[:72]
    return pwd_context.verify(plain_bytes, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hash a password with bcrypt.

    bcrypt has a hard 72-byte limit. Some platform builds silently truncate;
    others (notably Linux CI) raise ValueError. We truncate explicitly here for
    consistent cross-platform behavior. The Pydantic schema also enforces
    max_length=72 on user input, but this function is a last line of defense
    for any code path that bypasses schema validation (e.g., tests, direct calls).
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    now = datetime.now(UTC)
    lifetime = expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + lifetime
    to_encode.update({
        "exp": expire,
        "iat": now.timestamp(),
        "jti": str(uuid.uuid4()),
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

logger = logging.getLogger(__name__)

async def _resolve_firebase_user(decoded_token: dict, db: AsyncSession) -> Optional[User]:
    fb_email = decoded_token.get("email")
    if not fb_email:
        return None
    normalized_email = fb_email.lower().strip()
    result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
    user = result.scalars().first()

    if not user:
        full_name = decoded_token.get("name") or (normalized_email.split("@")[0] if "@" in normalized_email else "User")
        # Avoid ~400ms synchronous bcrypt hashing on the event loop when auto-provisioning
        # a Firebase-authenticated user; an unusable prefix sentinel cannot match verify_password.
        user = User(
            email=normalized_email,
            hashed_password=f"!firebase:{secrets.token_hex(16)}",
            full_name=full_name,
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC),
        )
        db.add(user)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
            user = result.scalars().first()
    else:
        token_name = decoded_token.get("name")
        if token_name and (not user.full_name or user.full_name == normalized_email.split("@")[0]):
            user.full_name = token_name
            try:
                await db.commit()
            except Exception:
                await db.rollback()

    if user:
        from app.core.logging import user_id_var
        user_id_var.set(str(user.id))
        return user
    return None


async def _resolve_user_full(token: str, db: AsyncSession) -> Optional[User]:
    decoded_token = None

    # 1. Attempt Firebase ID token verification first via firebase_admin
    try:
        import firebase_admin
        from firebase_admin import auth as fb_auth

        if not firebase_admin._apps:
            try:
                firebase_admin.initialize_app(options={"projectId": settings.GOOGLE_CLOUD_PROJECT or "mediskye-backend"})
            except Exception:
                try:
                    firebase_admin.initialize_app()
                except Exception:
                    pass

        if firebase_admin._apps:
            def _verify_fb_token():
                try:
                    return fb_auth.verify_id_token(token, check_revoked=True)
                except TypeError:
                    return fb_auth.verify_id_token(token)

            decoded_token = await asyncio.to_thread(_verify_fb_token)
    except Exception as e:
        logger.debug("Firebase Admin SDK verification deferred: %s", e)
        decoded_token = None

    # 1b. Fallback: Verify Firebase RS256 token using Google's public JWKS certificates directly
    if not decoded_token:
        try:
            unverified_header = jwt.get_unverified_header(token)
            if unverified_header.get("alg") == "RS256":
                project_id = settings.GOOGLE_CLOUD_PROJECT or "mediskye-backend"
                try:
                    jwks_client = jwt.PyJWKClient(
                        "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com",
                        cache_keys=True,
                    )
                    signing_key = jwks_client.get_signing_key_from_jwt(token)
                    decoded_token = jwt.decode(
                        token,
                        signing_key.key,
                        algorithms=["RS256"],
                        audience=project_id,
                        issuer=f"https://securetoken.google.com/{project_id}",
                    )
                except Exception as jwks_err:
                    if settings.DEBUG or settings.ENV == "development":
                        unverified = jwt.decode(token, options={"verify_signature": False})
                        if unverified.get("iss") == f"https://securetoken.google.com/{project_id}":
                            decoded_token = unverified
                        else:
                            logger.warning("JWKS token verification failed: %s", jwks_err)
                    else:
                        logger.warning("JWKS token verification failed: %s", jwks_err)
        except Exception:
            pass

    if decoded_token:
        firebase_info = decoded_token.get("firebase", {})
        sign_in_provider = firebase_info.get("sign_in_provider") if isinstance(firebase_info, dict) else None
        if decoded_token.get("email_verified") is False and sign_in_provider != "google.com":
            evict_token_cache_by_token(token)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified",
            )

        user = await _resolve_firebase_user(decoded_token, db)
        return user

    # 2. Local JWT decode fallback logic
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        jti: str = payload.get("jti")
        if email is None or jti is None:
            return None
    except jwt.InvalidTokenError:
        return None

    # Check if token is in Redis blocklist
    is_blocked = await redis_client.get(f"blocked_token:{jti}")
    if is_blocked:
        return None

    # Check if user signed out of all devices
    revoked_at = await redis_client.get(f"user_revoked_at:{email}")
    if revoked_at is not None:
        iat = payload.get("iat")
        try:
            if iat is None or float(iat) <= float(revoked_at):
                return None
        except (ValueError, TypeError):
            return None

    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    return user


async def get_current_user_full(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dedicated dependency for PHI-reading/mutating endpoints.
    Explicitly loads the full ORM User row with perf instrumentation and sets _phi_loaded=True.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    from app.core.logging import user_id_var

    t0 = time.perf_counter()

    # Fast path: the token was verified within the last 60s (by this or any other
    # endpoint). Skip Firebase/JWKS verification entirely and load the fresh ORM
    # row by primary key — PHI endpoints still get the full, current User object.
    cached_dto = get_cached_user_dto(token)
    if cached_dto is None:
        # Coalesce concurrent misses for the same token (parallel SPA requests).
        async with _single_flight(_hash_token(token)):
            cached_dto = get_cached_user_dto(token)
            if cached_dto is None:
                logger.info("AUTH CACHE MISS: resolving token %s", _short_hash(token))
                user = await _resolve_user_full(token, db)
                fetch_ms = (time.perf_counter() - t0) * 1000.0
                if not user:
                    raise credentials_exception
                logger.info("AUTH_PERF: get_current_user_full token resolution took %.2fms for user=%s", fetch_ms, user.id)
                user._phi_loaded = True
                cache_user_dto(token, _user_to_dto(user))
                user_id_var.set(str(user.id))
                return user

    user = await db.get(User, cached_dto.id)
    if user is None:
        # Account deleted since the token was cached — drop the stale entry.
        evict_token_cache_by_token(token)
        raise credentials_exception
    logger.info(
        "AUTH CACHE HIT: user %s (full ORM row loaded in %.2fms)",
        user.id,
        (time.perf_counter() - t0) * 1000.0,
    )
    user._phi_loaded = True
    user_id_var.set(str(user.id))
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> UserDTO:
    """
    High-performance dependency returning a lightweight Pydantic UserDTO.
    Uses in-memory 60s TTL cache to eliminate DB queries on the hot path.
    """
    from app.core.logging import user_id_var

    cached_dto = get_cached_user_dto(token)
    if cached_dto is None:
        # Coalesce concurrent misses for the same token (parallel SPA requests).
        async with _single_flight(_hash_token(token)):
            cached_dto = get_cached_user_dto(token)
            if cached_dto is None:
                logger.info("AUTH CACHE MISS: resolving token %s", _short_hash(token))
                user = await _resolve_user_full(token, db)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                dto = _user_to_dto(user)
                cache_user_dto(token, dto)
                user_id_var.set(str(dto.id))
                return dto

    logger.info("AUTH CACHE HIT: user %s", cached_dto.id)
    user_id_var.set(str(cached_dto.id))
    return cached_dto

