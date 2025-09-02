from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger


class JsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:  # type: ignore[override]
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("level"):
            log_record["level"] = record.levelname
        if not log_record.get("logger"):
            log_record["logger"] = record.name
        if record.exc_info and not log_record.get("exc_info"):
            log_record["exc_info"] = self.formatException(record.exc_info)


def setup_json_logging(level: str = "INFO") -> None:
    """Configure root logger to emit JSON logs to stdout."""
    root = logging.getLogger()
    root.setLevel(level)
    # Remove pre-existing handlers (e.g., from uvicorn default config)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = JsonFormatter("%(asctime)s %(level)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Tame noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)


