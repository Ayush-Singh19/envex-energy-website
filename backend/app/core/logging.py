"""JSON logging with a per-request ID.

Never log personal data (phone numbers, emails, message text). Log IDs instead.
"""

import logging
import sys
from contextvars import ContextVar

from pythonjsonlogger.json import JsonFormatter

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={"asctime": "ts", "levelname": "level", "name": "logger"},
        )
    )
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Access logs would duplicate our own request log line.
    logging.getLogger("uvicorn.access").disabled = True
