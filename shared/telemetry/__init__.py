"""
Shared telemetry library for production observability.

Provides:
- Structured JSON logging with correlation IDs
- Prometheus metrics collection
- OpenTelemetry distributed tracing
- Health check utilities
"""

from .logger import StructuredLogger, set_correlation_id, get_correlation_id
from .metrics import MetricsCollector, track_duration
from .tracer import setup_tracing, get_tracer

__all__ = [
    "StructuredLogger",
    "set_correlation_id",
    "get_correlation_id",
    "MetricsCollector",
    "track_duration",
    "setup_tracing",
    "get_tracer",
]
