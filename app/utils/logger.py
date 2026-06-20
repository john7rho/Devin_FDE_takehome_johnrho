import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

from app.core.config import settings

# Append-only JSONL log store (SPEC: "append-only log ... keyed on session ID").
# Every structured line is teed here as well as to stdout, so the API can query
# per-session logs at /api/v1/logs/{session_id}.
LOG_FILE: Optional[Path] = None


def _tee_to_file(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """structlog processor: append the (fully-built) event to the append-only
    JSONL store, then return it unchanged so JSONRenderer -> stdout still runs.
    Logging must never crash the app, so all I/O errors are swallowed."""
    if LOG_FILE is not None:
        try:
            with LOG_FILE.open("a") as f:
                f.write(json.dumps(event_dict, default=str) + "\n")
        except OSError:
            pass
    return event_dict


def setup_logging() -> None:
    """Configure structured logging: JSON to stdout AND to an append-only file,
    every line tagged with session_id (via contextvars merge)."""
    global LOG_FILE
    log_dir = Path(settings.log_path)
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG_FILE = log_dir / "sessions.jsonl"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            _tee_to_file,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(session_id: Optional[str] = None, **kwargs: Any) -> structlog.BoundLogger:
    """Get a logger with optional session_id context."""
    log = structlog.get_logger()
    if session_id:
        log = log.bind(session_id=session_id)
    if kwargs:
        log = log.bind(**kwargs)
    return log


class SessionLogger:
    """Logger that automatically includes session_id in all log entries."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = get_logger(session_id=session_id)

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(msg, **kwargs)

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(msg, **kwargs)

    def bind(self, **kwargs: Any) -> "SessionLogger":
        """Bind additional context to the logger."""
        self.logger = self.logger.bind(**kwargs)
        return self
