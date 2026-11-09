import asyncio
import hashlib
import html
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from firebase_admin import auth
from firebase_admin.auth import ActionCodeSettings, UserNotFoundError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.auth import (
    create_access_token,
    get_password_hash,
    oauth2_scheme,
    verify_password,
    get_current_user_full,
)
from app.core.audit import log_audit
from app.core.config import settings
from app.core.logging import logger
from app.core.limiter import limiter
from app.db.database import get_db
from app.db.models import User
from app.schemas.user import CustomVerificationRequest, Token, UserCreate, UserResponse
from app.services.email_service import send_email_via_gmail

router = APIRouter(tags=["Authentication"])
CUSTOM_AUTH_ACTION_URL = "https://mediskye.pages.dev/auth/action"


def _build_custom_action_link(firebase_link: str, mode: str) -> str:
    oob_code = parse_qs(urlsplit(firebase_link).query).get("oobCode", [None])[0]
    if not oob_code:
        raise ValueError("Firebase action link did not include an out-of-band code")
    return f"{CUSTOM_AUTH_ACTION_URL}?{urlencode({'mode': mode, 'oobCode': oob_code})}"


def _build_mediskye_email_html(
    *,
    preheader: str,
    badge_label: str,
    heading: str,
    intro_text: str,
    recipient_email: str,
    cta_label: str,
    action_url: str,
    security_note: str,
) -> str:
    """Render a responsive, brand-aligned transactional HTML email for MediSkye."""
    safe_email = html.escape(recipient_email)
    safe_url = html.escape(action_url, quote=True)

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light dark" />
  <meta name="supported-color-schemes" content="light dark" />
  <title>{html.escape(heading)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #07090e; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #e2e8f0;">
  <div style="display: none; max-height: 0; overflow: hidden; opacity: 0; font-size: 1px; line-height: 1px; color: #07090e;">
    {html.escape(preheader)}&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#07090e" style="background-color: #07090e; width: 100%; margin: 0; padding: 36px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#0d121a" style="max-width: 560px; width: 100%; background-color: #0d121a; border: 1px solid #1e293b; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);">
          <tr>
            <td height="4" bgcolor="#06b6d4" style="background: linear-gradient(90deg, #06b6d4 0%, #38bdf8 100%); font-size: 0; line-height: 0;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding: 28px 32px 20px; border-bottom: 1px solid #172030;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="left" valign="middle">
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                      <tr>
                        <td width="32" height="32" align="center" valign="middle" bgcolor="#ffffff" style="width: 32px; height: 32px; background-color: #ffffff; border-radius: 8px; font-weight: 800; font-size: 16px; color: #07090e; font-family: monospace;">M</td>
                        <td style="padding-left: 12px;">
                          <span style="font-size: 18px; font-weight: 700; color: #f8fafc; letter-spacing: -0.3px;">MediSkye</span>
                          <span style="display: block; font-size: 11px; font-weight: 500; color: #64748b; letter-spacing: 0.4px; text-transform: uppercase;">Clinical AI Platform</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                  <td align="right" valign="middle">
                    <span style="display: inline-block; padding: 5px 10px; background-color: #0c2530; border: 1px solid #155e75; border-radius: 999px; font-size: 11px; font-weight: 600; color: #22d3ee; letter-spacing: 0.5px; text-transform: uppercase;">{html.escape(badge_label)}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 32px 32px 24px;">
              <h1 style="margin: 0 0 14px; font-size: 24px; line-height: 1.3; font-weight: 700; color: #f8fafc; letter-spacing: -0.4px;">{html.escape(heading)}</h1>
              <p style="margin: 0 0 16px; font-size: 15px; line-height: 1.65; color: #cbd5e1;">{html.escape(intro_text)}</p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 0 0 26px;">
                <tr>
                  <td bgcolor="#111824" style="background-color: #111824; border: 1px solid #1e293b; border-radius: 10px; padding: 11px 14px; font-size: 13px; color: #94a3b8;">
                    Account: <strong style="color: #f1f5f9; font-weight: 600;">{safe_email}</strong>
                  </td>
                </tr>
              </table>
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 0 0 28px;">
                <tr>
                  <td align="center" bgcolor="#06b6d4" style="border-radius: 10px; background-color: #06b6d4;">
                    <a href="{safe_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; padding: 14px 28px; font-size: 15px; font-weight: 700; color: #041318; text-decoration: none; border-radius: 10px; letter-spacing: -0.1px;">{html.escape(cta_label)} &rarr;</a>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 0 0 24px;">
                <tr>
                  <td bgcolor="#111824" style="background-color: #111824; border-left: 3px solid #06b6d4; border-radius: 4px 8px 8px 4px; padding: 12px 16px;">
                    <p style="margin: 0; font-size: 13px; line-height: 1.55; color: #94a3b8;">
                      <strong style="color: #e2e8f0;">Security Notice:</strong> This single-use link expires in <strong style="color: #e2e8f0;">60 minutes</strong>. {html.escape(security_note)}
                    </p>
                  </td>
                </tr>
              </table>
              <p style="margin: 0 0 8px; font-size: 12px; font-weight: 500; color: #64748b;">Button not working? Copy and paste this URL into your browser:</p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td bgcolor="#07090e" style="background-color: #07090e; border: 1px solid #1e293b; border-radius: 8px; padding: 10px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 11px; line-height: 1.5; color: #38bdf8; word-break: break-all; overflow-wrap: anywhere;">
                    <a href="{safe_url}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; text-decoration: underline; word-break: break-all; overflow-wrap: anywhere;">{safe_url}</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td bgcolor="#090d14" style="background-color: #090d14; padding: 22px 32px; border-top: 1px solid #172030;">
              <p style="margin: 0 0 8px; font-size: 12px; line-height: 1.5; color: #64748b;">
                <strong style="color: #94a3b8;">MediSkye AI</strong> &bull; <a href="https://mediskye.pages.dev" style="color: #22d3ee; text-decoration: none;">mediskye.pages.dev</a>
              </p>
              <p style="margin: 0; font-size: 11px; line-height: 1.5; color: #475569;">
                MediSkye is an informational clinical AI assistant designed for health literacy purposes only and is not a substitute for professional medical advice, diagnosis, or treatment.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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
        username_hash = hashlib.sha256(normalized_username.encode("utf-8")).hexdigest()[:16]
        await log_audit(db, "FAILED_LOGIN", None, f"user_hash:{username_hash}", client_ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    await log_audit(db, "SUCCESSFUL_LOGIN", user.id, "auth", client_ip)
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    token: str = Depends(oauth2_scheme),
    user: User = Depends(get_current_user_full),
    db: AsyncSession = Depends(get_db),
):
    """
    Logout the user by setting token_invalid_before in the database and adding JWT to the Redis blocklist.
    """
    import jwt, time
    from app.core.auth import (
        SECRET_KEY,
        ALGORITHM,
        evict_token_cache_by_token,
        evict_token_cache_for_user,
        mark_token_revoked_in_memory,
    )
    from app.core.redis_client import redis_client

    mark_token_revoked_in_memory(token)
    evict_token_cache_by_token(token)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti, exp = payload.get("jti"), payload.get("exp")
        if jti and exp:
            ttl = int(exp - time.time())
            if ttl > 0:
                await redis_client.setex(f"blocked_token:{jti}", ttl, "true")
    except jwt.InvalidTokenError:
        pass

    user.token_invalid_before = datetime.now(UTC)
    db.add(user)
    await db.commit()
    evict_token_cache_for_user(user.id)
    return {"message": "Successfully logged out"}


async def _send_email_background(to_email: str, subject: str, html_body: str) -> None:
    """Async background worker for non-blocking Gmail SMTP dispatch."""
    try:
        await send_email_via_gmail(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
        )
    except Exception as e:
        import sentry_sdk
        sentry_sdk.capture_exception(e)
        logger.exception("Failed to send background email to %s", to_email)


@router.post("/auth/send-custom-verification")
@router.post("/send-custom-verification")
@limiter.limit("3/minute")
async def send_custom_verification(
    request: Request,
    verification_req: CustomVerificationRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Generate an email verification link and send the branded email via Gmail SMTP.
    """
    email = str(verification_req.email)
    try:
        action_code_settings = ActionCodeSettings(
            url=CUSTOM_AUTH_ACTION_URL,
            handle_code_in_app=True,
        )
        firebase_link = await asyncio.to_thread(
            auth.generate_email_verification_link,
            email,
            action_code_settings=action_code_settings,
        )
        link = _build_custom_action_link(firebase_link, "verifyEmail")
    except UserNotFoundError:
        logger.warning("Verification requested for non-existent user: %s", email)
        return {"message": "Verification email sent"}
    except Exception:
        logger.exception("Failed to generate verification link for %s", email)
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    html_content = _build_mediskye_email_html(
        preheader="Confirm your email address to activate your MediSkye clinical workspace.",
        badge_label="Verify Account",
        heading="Verify your email address",
        intro_text=(
            "Welcome to MediSkye. Confirm your email address below to activate your "
            "encrypted workspace and start analyzing your laboratory and medical reports."
        ),
        recipient_email=email,
        cta_label="Verify Email Address",
        action_url=link,
        security_note="If you did not create a MediSkye account, you can safely disregard this email.",
    )

    is_sync = False
    if getattr(settings, "ENV", "").lower() == "test":
        sync_header = request.headers.get("X-Sync-Email-Test")
        if sync_header == "0":
            is_sync = False
        else:
            is_sync = True

    if is_sync:
        try:
            await send_email_via_gmail(
                to_email=email,
                subject="Verify your email address — MediSkye",
                html_body=html_content,
            )
        except Exception:
            logger.exception("Failed to send verification email to %s", email)
            raise HTTPException(status_code=502, detail="Email service is currently unavailable. Please try again later.")
    else:
        background_tasks.add_task(
            _send_email_background,
            email,
            "Verify your email address — MediSkye",
            html_content,
        )

    return {"message": "Verification email sent"}


@router.post("/auth/send-custom-password-reset")
@router.post("/send-custom-password-reset")
@limiter.limit("3/minute")
async def send_custom_password_reset(
    request: Request,
    reset_req: CustomVerificationRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Generate a password reset link and send the branded email via Gmail SMTP.
    """
    email = str(reset_req.email)
    try:
        action_code_settings = ActionCodeSettings(
            url=CUSTOM_AUTH_ACTION_URL,
            handle_code_in_app=True,
        )
        firebase_link = await asyncio.to_thread(
            auth.generate_password_reset_link,
            email,
            action_code_settings=action_code_settings,
        )
        link = _build_custom_action_link(firebase_link, "resetPassword")
    except Exception:
        # IMPORTANT: Do NOT leak if the user exists or not.
        # Return a 200 OK with a generic success message to prevent user enumeration attacks.
        return {"message": "If an account exists with this email, a reset link has been sent."}

    html_content = _build_mediskye_email_html(
        preheader="Use this secure link to reset your MediSkye account password.",
        badge_label="Password Reset",
        heading="Reset your MediSkye password",
        intro_text=(
            "We received a request to reset the password for your MediSkye account. "
            "Select the button below to choose a new password."
        ),
        recipient_email=email,
        cta_label="Reset Password",
        action_url=link,
        security_note=(
            "If you did not request a password reset, no action is needed—"
            "your current password will remain unchanged."
        ),
    )

    is_sync = False
    if getattr(settings, "ENV", "").lower() == "test":
        sync_header = request.headers.get("X-Sync-Email-Test")
        if sync_header == "0":
            is_sync = False
        else:
            is_sync = True

    if is_sync:
        try:
            await send_email_via_gmail(
                to_email=email,
                subject="Reset your password — MediSkye",
                html_body=html_content,
            )
        except Exception:
            logger.exception("Failed to send password reset email to %s", email)
            raise HTTPException(status_code=502, detail="Email service is currently unavailable. Please try again later.")
    else:
        background_tasks.add_task(
            _send_email_background,
            email,
            "Reset your password — MediSkye",
            html_content,
        )

    return {"message": "If an account exists with this email, a reset link has been sent."}

    return {"message": "If an account exists with this email, a reset link has been sent."}
