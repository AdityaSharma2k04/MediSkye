import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from typing import Any

from app.core.auth import get_password_hash, verify_password, create_access_token, oauth2_scheme
from app.db.database import get_db
from app.db.models import User
from app.schemas.user import UserCreate, UserResponse, Token, CustomVerificationRequest
from app.core.audit import log_audit
from datetime import datetime, UTC
from fastapi import Request
from app.core.limiter import limiter
from app.core.config import settings
from app.core.logging import logger
import resend
from resend.exceptions import ResendError
from firebase_admin import auth

router = APIRouter(tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")
async def register(request: Request, user_in: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Register a new user.
    """
    normalized_email = user_in.email.lower().strip()
    result = await db.execute(select(User).filter(func.lower(User.email) == normalized_email))
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
    
    try:
        hashed_pwd = await asyncio.to_thread(get_password_hash, user_in.password)
        user = User(
            email=normalized_email,
            hashed_password=hashed_pwd,
            phi_consent_granted=True,
            consent_timestamp=datetime.now(UTC)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    client_ip = request.client.host if request.client else "unknown"
    await log_audit(db, "USER_REGISTERED", user.id, "auth", client_ip)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(request: Request, db: AsyncSession = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = form_data.username.lower().strip()
    result = await db.execute(select(User).filter(func.lower(User.email) == normalized_username))
    user = result.scalars().first()
    password_ok = (
        await asyncio.to_thread(verify_password, form_data.password, user.hashed_password)
        if user else False
    )
    if not user or not password_ok:
        await log_audit(db, "FAILED_LOGIN", None, form_data.username, client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    
    await log_audit(db, "SUCCESSFUL_LOGIN", user.id, "auth", client_ip)
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout the user by adding their JWT to the Redis blocklist.
    """
    import jwt
    from app.core.auth import SECRET_KEY, ALGORITHM, evict_token_cache_by_token
    from app.core.redis_client import redis_client
    # Drop the 60s auth-cache entry first so the revoked token cannot be served
    # from memory (cache hits skip the Redis blocklist check by design).
    evict_token_cache_by_token(token)
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


@router.post("/auth/send-custom-verification")
@router.post("/send-custom-verification")
@limiter.limit("3/minute")
async def send_custom_verification(
    request: Request,
    verification_req: CustomVerificationRequest,
) -> Any:
    """
    Generate email verification link with Firebase Admin SDK and send custom branded email via Resend.
    """
    email = str(verification_req.email)
    try:
        link = await asyncio.to_thread(auth.generate_email_verification_link, email)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Could not generate link. User may not exist.")

    resend.api_key = settings.RESEND_API_KEY

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <h2 style="color: #06b6d4;">Welcome to MediSkye 🩺</h2>
        <p>Hi there,</p>
        <p>You're one step away from understanding your medical reports. Please verify your email address by clicking the button below:</p>
        <a href="{link}" style="display: inline-block; padding: 12px 24px; background-color: #06b6d4; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0;">Verify my email</a>
        <p style="font-size: 12px; color: #666;">If the button doesn't work, copy and paste this link: <br>{link}</p>
        <p style="font-size: 12px; color: #666;">This link will expire in 1 hour. If you didn't request this, please ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;" />
        <p style="font-size: 12px; color: #999;">MediSkye is an educational tool, not a substitute for professional medical advice.</p>
    </div>
    """

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": f"MediSkye <{settings.FROM_EMAIL}>",
                "to": email,
                "subject": "Verify your email to start using MediSkye 🩺",
                "html": html_content,
            },
        )
    except ResendError as e:
        logger.error(f"Resend API error: {e}")
        raise HTTPException(status_code=502, detail="Email service is currently unavailable. Please try again later.")

    return {"message": "Verification email sent"}


@router.post("/auth/send-custom-password-reset")
@router.post("/send-custom-password-reset")
@limiter.limit("3/minute")
async def send_custom_password_reset(
    request: Request,
    reset_req: CustomVerificationRequest,
) -> Any:
    """
    Generate password reset link via Firebase Admin SDK and send custom branded email via Resend.
    """
    email = str(reset_req.email)
    try:
        link = await asyncio.to_thread(auth.generate_password_reset_link, email)
    except Exception as e:
        # IMPORTANT: Do NOT leak if the user exists or not.
        # Return a 200 OK with a generic success message to prevent user enumeration attacks.
        return {"message": "If an account exists with this email, a reset link has been sent."}

    resend.api_key = settings.RESEND_API_KEY

    html_content = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
        <h2 style="color: #06b6d4;">Reset your MediSkye Password 🔒</h2>
        <p>Hi there,</p>
        <p>We received a request to reset the password for your MediSkye account. Click the button below to choose a new password:</p>
        <a href="{link}" style="display: inline-block; padding: 12px 24px; background-color: #06b6d4; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0;">Reset my password</a>
        <p style="font-size: 12px; color: #666;">If the button doesn't work, copy and paste this link: <br>{link}</p>
        <p style="font-size: 12px; color: #666;">This link will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email. Your password will not change.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;" />
        <p style="font-size: 12px; color: #999;">MediSkye is an educational tool, not a substitute for professional medical advice.</p>
    </div>
    """

    try:
        await asyncio.to_thread(
            resend.Emails.send,
            {
                "from": f"MediSkye <{settings.FROM_EMAIL}>",
                "to": email,
                "subject": "Reset your MediSkye password 🔒",
                "html": html_content,
            },
        )
    except ResendError as e:
        logger.error(f"Resend API error: {e}")
        raise HTTPException(status_code=502, detail="Email service is currently unavailable. Please try again later.")

    return {"message": "If an account exists with this email, a reset link has been sent."}
