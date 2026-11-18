import uuid

from app.core.logging import request_id_var, user_id_var
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        token_req = request_id_var.set(request_id)
        user_id = getattr(request.state, "user_id", None) or ""
        token_user = user_id_var.set(str(user_id) if user_id else "")
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token_req)
            user_id_var.reset(token_user)
