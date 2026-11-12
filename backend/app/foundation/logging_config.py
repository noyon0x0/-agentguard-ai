"""Minimal structured logging that avoids request bodies and credentials."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone


class SafeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "event": record.getMessage(),
                **{
                    key: getattr(record, key)
                    for key in ("method", "status_code", "error_type")
                    if getattr(record, key, None) is not None
                },
            },
            ensure_ascii=True,
        )


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
