"""
Prometheus metrics collection for production monitoring.
"""

import time
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Generator

from prometheus_client import Counter, Gauge, Histogram, Summary


class MetricsCollector:
    """
    Production-grade metrics collector using Prometheus.

    Features:
    - Request/response metrics (latency, errors, throughput)
    - Performance metrics (CPU, memory, records/sec)
    - Security metrics (rate limits, attacks blocked)
    - Business metrics (files processed, sentiment distribution)
    - Zero-cost (self-hosted Prometheus on free tier)
    """

    # HTTP metrics
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )

    http_request_duration_seconds = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    )

    # Processing metrics
    records_processed_total = Counter(
        "records_processed_total",
        "Total records processed",
        ["layer", "operation"],
    )

    processing_duration_seconds = Histogram(
        "processing_duration_seconds",
        "Processing duration per operation",
        ["layer", "operation"],
        buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    )

    records_per_second = Gauge(
        "records_per_second",
        "Current throughput (records/sec)",
        ["layer"],
    )

    # Data quality metrics
    data_quality_issues_total = Counter(
        "data_quality_issues_total",
        "Total data quality issues detected",
        ["issue_type"],
    )

    null_values_percentage = Gauge(
        "null_values_percentage",
        "Percentage of null values in key fields",
        ["field"],
    )

    # Security metrics
    security_events_total = Counter(
        "security_events_total",
        "Total security events",
        ["event_type", "severity"],
    )

    rate_limit_hits_total = Counter(
        "rate_limit_hits_total",
        "Rate limit hits",
        ["endpoint"],
    )

    injection_attacks_blocked_total = Counter(
        "injection_attacks_blocked_total",
        "Injection attacks blocked",
        ["attack_type"],
    )

    # Business metrics
    files_processed_total = Counter(
        "files_processed_total",
        "Total files processed",
        ["file_type", "status"],
    )

    sentiment_distribution = Gauge(
        "sentiment_distribution",
        "Sentiment distribution",
        ["sentiment"],
    )

    # System metrics
    memory_usage_bytes = Gauge(
        "memory_usage_bytes",
        "Current memory usage",
        ["component"],
    )

    active_requests = Gauge(
        "active_requests",
        "Number of active requests",
    )

    # Model metrics
    model_inference_duration_seconds = Histogram(
        "model_inference_duration_seconds",
        "Model inference latency",
        ["model_name"],
        buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0],
    )

    @classmethod
    def record_http_request(
        cls,
        method: str,
        endpoint: str,
        status: int,
        duration_seconds: float,
    ) -> None:
        """Record HTTP request metrics."""
        cls.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status),
        ).inc()
        cls.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_seconds)

    @classmethod
    def record_processing(
        cls,
        layer: str,
        operation: str,
        records: int,
        duration_seconds: float,
    ) -> None:
        """Record processing metrics."""
        cls.records_processed_total.labels(
            layer=layer,
            operation=operation,
        ).inc(records)
        cls.processing_duration_seconds.labels(
            layer=layer,
            operation=operation,
        ).observe(duration_seconds)

        # Update throughput gauge
        if duration_seconds > 0:
            cls.records_per_second.labels(layer=layer).set(
                records / duration_seconds
            )

    @classmethod
    def record_data_quality_issue(cls, issue_type: str, count: int = 1) -> None:
        """Record data quality issue."""
        cls.data_quality_issues_total.labels(issue_type=issue_type).inc(count)

    @classmethod
    def record_security_event(cls, event_type: str, severity: str) -> None:
        """Record security event."""
        cls.security_events_total.labels(
            event_type=event_type,
            severity=severity,
        ).inc()

    @classmethod
    def record_injection_attack_blocked(cls, attack_type: str, count: int = 1) -> None:
        """Record blocked injection attack."""
        cls.injection_attacks_blocked_total.labels(attack_type=attack_type).inc(count)

    @classmethod
    def record_file_processed(cls, file_type: str, status: str) -> None:
        """Record file processing result."""
        cls.files_processed_total.labels(
            file_type=file_type,
            status=status,
        ).inc()

    @classmethod
    @contextmanager
    def track_active_request(cls) -> Generator[None, None, None]:
        """Context manager to track active requests."""
        cls.active_requests.inc()
        try:
            yield
        finally:
            cls.active_requests.dec()


def track_duration(layer: str, operation: str) -> Callable:
    """
    Decorator to track operation duration and throughput.

    Usage:
        @track_duration("input-layer", "upload")
        def upload_file(file):
            return process(file)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # Try to get record count from result
            records = 0
            if isinstance(result, dict) and "records_processed" in result:
                records = result["records_processed"]
            elif hasattr(result, "height"):  # Polars DataFrame
                records = result.height
            elif hasattr(result, "__len__"):
                records = len(result)

            MetricsCollector.record_processing(layer, operation, records, duration)
            return result

        return wrapper

    return decorator
