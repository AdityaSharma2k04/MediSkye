import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.logging import logger
from app.core.config import settings


async def global_exception_handler(request: Request, exc: Exception):
    # Log detailed traceback internally
    logger.error(
        f"Unhandled Exception on {request.method} {request.url.path}: {exc}\n"
        f"{traceback.format_exc()}"
    )

    # Return sanitized user-friendly error response without exposing internal details
    message = "An unexpected server error occurred. Please try again later."
    if settings.DEBUG:
        message = str(exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": message, "error_code": "INTERNAL_SERVER_ERROR"},
    )
