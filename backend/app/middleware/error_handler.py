import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.logging import logger
from app.core.config import settings


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    req_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "request_id": req_id,
        },
        headers=getattr(exc, "headers", None),
    )


async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "")
    import sentry_sdk
    sentry_sdk.capture_exception(exc)

    # Log detailed traceback internally
    logger.error(
        f"Unhandled Exception on {request.method} {request.url.path} (request_id={req_id}): {exc}\n"
        f"{traceback.format_exc()}"
    )

    # Return sanitized user-friendly error response without exposing internal details
    message = "An unexpected server error occurred. Please try again later."
    if settings.DEBUG:
        message = str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": message,
            "error_code": "INTERNAL_SERVER_ERROR",
            "request_id": req_id,
        },
    )
