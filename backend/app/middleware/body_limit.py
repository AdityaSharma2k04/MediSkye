from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

MAX_JSON_BODY_BYTES = 1_048_576  # 1MB limit for JSON payloads


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects JSON payloads larger than 1MB with HTTP 413 Payload Too Large.
    Multipart uploads (e.g. /upload) are explicitly excluded to allow up to 50MB documents.
    """

    async def dispatch(self, request, call_next):
        content_type = request.headers.get("content-type", "").lower()
        if content_type.startswith("application/json"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > MAX_JSON_BODY_BYTES:
                        req_id = getattr(request.state, "request_id", "")
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": "Request body too large. JSON payloads must not exceed 1MB.",
                                "request_id": req_id,
                            },
                        )
                except ValueError:
                    pass
        return await call_next(request)
