import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_key(request: Request) -> str:
    """On Cloud Run the TCP peer is Google's front end. Use the client IP Google
    appends as the LAST X-Forwarded-For entry (earlier entries are spoofable)."""
    if os.getenv("K_SERVICE"):  # set automatically on Cloud Run only
        xff = request.headers.get("x-forwarded-for", "")
        last = xff.split(",")[-1].strip() if xff else ""
        if last:
            return last
    return get_remote_address(request)


limiter = Limiter(key_func=client_key, storage_uri="memory://")
