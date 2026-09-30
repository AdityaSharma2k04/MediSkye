from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Any

from app.core.auth import get_password_hash, verify_password, create_access_token, oauth2_scheme
from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserResponse, Token
from app.core.audit import log_audit
from datetime import datetime
from fastapi import Request

router = APIRouter(tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
async def register(request: Request, user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Register a new user.
    """
    result = await db.execute(select(User).filter(User.email == user_in.email))
    user = result.scalars().first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    if not user_in.phi_consent_granted:
        raise HTTPException(
            status_code=400,
            detail="You must consent to PHI processing to register.",
        )
    
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        phi_consent_granted=True,
        consent_timestamp=datetime.utcnow()
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await log_audit(db, "USER_REGISTERED", user.id, "auth", request.client.host)
    return user


@router.post("/login", response_model=Token)
async def login(request: Request, db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    result = await db.execute(select(User).filter(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        await log_audit(db, "FAILED_LOGIN", None, form_data.username, request.client.host)
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    await log_audit(db, "SUCCESSFUL_LOGIN", user.id, "auth", request.client.host)
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout the user by adding their JWT to the Redis blocklist.
    """
    import jwt
    from app.core.auth import SECRET_KEY, ALGORITHM
    from app.core.redis_client import redis_client
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            import time
            ttl = int(exp - time.time())
            if ttl > 0:
                await redis_client.setex(f"blocked_token:{jti}", ttl, "true")
        return {"message": "Successfully logged out"}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
