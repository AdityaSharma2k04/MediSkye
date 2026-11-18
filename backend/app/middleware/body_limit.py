from fastapi import HTTPException
from fastapi.responses import JSONResponse

MAX_JSON_BODY_BYTES = 1_048_576  # 1MB limit for JSON payloads
MAX_UPLOAD_BODY_BYTES = 51 * 1024 * 1024  # 51MB (50MB document + 1MB buffer)


class BodySizeLimitMiddleware:
    """
    Pure-ASGI byte-counting body limit middleware.
    Enforces 1MB on JSON requests and 51MB on /upload requests by checking
    the Content-Length header and counting streaming chunks in ASGI receive.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        headers = dict(scope.get("headers", []))
        content_type = headers.get(b"content-type", b"").decode("latin1", "replace").lower()

        if "/upload" in path:
            max_bytes = MAX_UPLOAD_BODY_BYTES
            detail = "Request body too large. Upload payloads must not exceed 51MB."
        elif content_type.startswith("application/json"):
            max_bytes = MAX_JSON_BODY_BYTES
            detail = "Request body too large. JSON payloads must not exceed 1MB."
        else:
            max_bytes = None
            detail = ""

        if max_bytes is not None:
            # 1. Pre-flight check via Content-Length header
            cl_header = headers.get(b"content-length")
            if cl_header:
                try:
                    if int(cl_header.decode("latin1")) > max_bytes:
                        response = JSONResponse(
                            status_code=413,
                            content={"detail": detail},
                        )
                        await response(scope, receive, send)
                        return
                except ValueError:
                    pass

            # 2. Byte-counting wrapped receive for streamed/chunked payloads
            bytes_received = 0

            async def custom_receive():
                nonlocal bytes_received
                message = await receive()
                if message["type"] == "http.request":
                    body = message.get("body", b"")
                    bytes_received += len(body)
                    if bytes_received > max_bytes:
                        raise HTTPException(status_code=413, detail=detail)
                return message

            try:
                await self.app(scope, custom_receive, send)
            except HTTPException as exc:
                if exc.status_code == 413:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": exc.detail},
                    )
                    await response(scope, receive, send)
                else:
                    raise
            return

        await self.app(scope, receive, send)
