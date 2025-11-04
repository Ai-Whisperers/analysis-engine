"""
Structured JSON logging with correlation IDs for request tracing.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

# Context variable for correlation ID (thread-safe, async-safe)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context (request/task)."""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current context."""
    return _correlation_id.get()


class StructuredLogger:
    """
    Production-grade JSON logger with structured fields.

    Features:
    - JSON output for log aggregation (ELK, Loki, etc.)
    - Correlation IDs for distributed tracing
    - Performance tracking (duration, memory)
    - Security event logging
    - Zero-cost (no external service required)
    """

    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        output_stream=sys.stdout,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []  # Clear existing handlers

        # JSON formatter
        handler = logging.StreamHandler(output_stream)
        handler.setFormatter(self._JSONFormatter())
        self.logger.addHandler(handler)

    class _JSONFormatter(logging.Formatter):
        """Format log records as JSON."""

        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "correlation_id": get_correlation_id(),
            }

            # Add extra fields from record
            if hasattr(record, "extra_fields"):
                log_data.update(record.extra_fields)

            # Add exception info
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data)

    def _log(self, level: int, message: str, **extra_fields: Any) -> None:
        """Internal logging method with extra fields."""
        extra = {"extra_fields": extra_fields} if extra_fields else {}
        self.logger.log(level, message, extra=extra)

    def debug(self, message: str, **extra_fields: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **extra_fields)

    def info(self, message: str, **extra_fields: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **extra_fields)

    def warning(self, message: str, **extra_fields: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **extra_fields)

    def error(self, message: str, **extra_fields: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, **extra_fields)

    def critical(self, message: str, **extra_fields: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, **extra_fields)

    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        records_processed: int = 0,
        **extra_fields: Any,
    ) -> None:
        """Log performance metrics."""
        self.info(
            f"Performance: {operation}",
            operation=operation,
            duration_ms=round(duration_ms, 2),
            records_processed=records_processed,
            throughput_per_sec=round(records_processed / (duration_ms / 1000), 2)
            if duration_ms > 0
            else 0,
            **extra_fields,
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        **extra_fields: Any,
    ) -> None:
        """Log security events (attacks, rate limits, etc.)."""
        self.warning(
            f"Security: {event_type}",
            event_type=event_type,
            severity=severity,
            description=description,
            **extra_fields,
        )

    def log_data_quality(
        self,
        issue_type: str,
        records_affected: int,
        total_records: int,
        **extra_fields: Any,
    ) -> None:
        """Log data quality issues."""
        self.info(
            f"Data Quality: {issue_type}",
            issue_type=issue_type,
            records_affected=records_affected,
            total_records=total_records,
            percentage=round((records_affected / total_records) * 100, 2)
            if total_records > 0
            else 0,
            **extra_fields,
        )
