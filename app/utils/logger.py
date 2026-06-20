import logging
from pathlib import Path
from typing import Optional

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging with session_id tagging."""
    Path(settings.log_path).mkdir(parents=True, exist_ok=True)
    
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(session_id: Optional[str] = None, **kwargs) -> structlog.BoundLogger:
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
    
    def info(self, msg: str, **kwargs) -> None:
        self.logger.info(msg, **kwargs)
    
    def error(self, msg: str, **kwargs) -> None:
        self.logger.error(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs) -> None:
        self.logger.warning(msg, **kwargs)
    
    def debug(self, msg: str, **kwargs) -> None:
        self.logger.debug(msg, **kwargs)
    
    def bind(self, **kwargs) -> "SessionLogger":
        """Bind additional context to the logger."""
        self.logger = self.logger.bind(**kwargs)
        return self
