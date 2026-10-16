import uuid
from datetime import datetime, timedelta, UTC
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
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
    # Default to the configured lifetime (7 days) instead of an unconfigured
    # 15-minute value that was logging users out mid-session.
    lifetime = expires_delta if expires_delta is not None else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + lifetime
    to_encode.update({
        "exp": expire,
        "iat": now.timestamp(),
        "jti": str(uuid.uuid4()),
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        jti: str = payload.get("jti")
        if email is None or jti is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
    
    # Check if token is in Redis blocklist
    is_blocked = await redis_client.get(f"blocked_token:{jti}")
    if is_blocked:
        raise credentials_exception

    # Check if user signed out of all devices
    revoked_at = await redis_client.get(f"user_revoked_at:{email}")
    if revoked_at is not None:
        iat = payload.get("iat")
        try:
            if iat is None or float(iat) <= float(revoked_at):
                raise credentials_exception
        except (ValueError, TypeError):
            raise credentials_exception
    
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    from app.core.logging import user_id_var
    user_id_var.set(str(user.id))
    return user

