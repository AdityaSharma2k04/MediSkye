import json
import logging
import sys
import contextvars
from datetime import datetime, timezone
from app.core.config import settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="")


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Suppress noise from health checks if needed
        return True


class JSONFormatter(logging.Formatter):
    """
    Structured JSON log formatter for production observability.
    Outputs: timestamp, level, logger, message, request_id, user_id.
    """

    def format(self, record: logging.LogRecord) -> str:
        req_id = getattr(record, "request_id", None) or request_id_var.get() or ""
        uid = getattr(record, "user_id", None) or user_id_var.get() or ""

        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": req_id,
            "user_id": uid,
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging():
    """
    Configure root logging handler.
    If ENV == 'production', use JSONFormatter.
    Otherwise (e.g. 'development', 'test'), use human-readable text format.
    """
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to prevent duplicate lines
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if settings.ENV == "production":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )

    root_logger.addHandler(handler)

    # Silence verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)


logger = logging.getLogger("mediskye")
