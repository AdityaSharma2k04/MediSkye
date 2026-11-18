import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
try:
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration as SqlAlchemyIntegration
except ImportError:
    from sentry_sdk.integrations.sqlalchemy import SqlAlchemyIntegration

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "email", "authorization", "password", "token", "id_token",
    "health_profile", "phi", "lab_results", "document_text",
    "query", "message", "prompt", "response", "caregiver",
}

def _scrub(obj):
    if isinstance(obj, dict):
        return {
            k: ("[scrubbed]" if k.lower() in SENSITIVE_KEYS else _scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 256:
        return obj[:256] + "...[truncated]"
    return obj

def _before_send(event, hint=None):
    event.pop("request", None)
    event.pop("user", None)
    event.pop("breadcrumbs", None)
    if "extra" in event:
        event["extra"] = _scrub(event["extra"])
    if "contexts" in event:
        event["contexts"] = _scrub(event["contexts"])
    if "exception" in event:
        for exc in event["exception"].get("values", []):
            if "value" in exc:
                exc["value"] = "[scrubbed exception message]"
    return event

def init_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return  # no-op in dev/CI; enabled only when DSN present
    
    # Strip hidden whitespaces or quotes that Cloud Run secrets often inject
    dsn = dsn.strip().strip('"').strip("'")
    
    if not dsn.startswith("https://"):
        logger.warning("Invalid SENTRY_DSN format. Sentry disabled.")
        return

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("SENTRY_RELEASE"),
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlAlchemyIntegration(),
            ],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.0,
            send_default_pii=False,
            max_request_body_size="never",
            include_local_variables=False,
            before_send=_before_send,
            before_send_transaction=_before_send,
        )
        logger.info("Sentry initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}. Application will continue running without Sentry.")
        # We DO NOT raise the exception. The app must start!