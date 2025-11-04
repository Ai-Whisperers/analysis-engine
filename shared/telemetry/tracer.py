"""
OpenTelemetry distributed tracing for request flow visibility.
"""

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_tracing(
    service_name: str = "dataset-analyzer",
    jaeger_host: Optional[str] = None,
    jaeger_port: int = 6831,
    enable_console: bool = False,
) -> None:
    """
    Setup OpenTelemetry distributed tracing.

    Features:
    - Jaeger integration (self-hosted on free tier)
    - Automatic FastAPI instrumentation
    - Request flow visualization
    - Performance bottleneck identification
    - Zero-cost (self-hosted Jaeger)

    Args:
        service_name: Name of the service (for Jaeger UI)
        jaeger_host: Jaeger agent host (None = disabled)
        jaeger_port: Jaeger agent port (default: 6831)
        enable_console: Enable console export for debugging

    Environment variables:
        JAEGER_AGENT_HOST: Jaeger agent hostname
        JAEGER_AGENT_PORT: Jaeger agent port
        OTEL_CONSOLE_EXPORT: Enable console export (true/false)
    """
    # Check environment variables
    jaeger_host = jaeger_host or os.getenv("JAEGER_AGENT_HOST")
    jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", jaeger_port))
    enable_console = enable_console or os.getenv("OTEL_CONSOLE_EXPORT", "").lower() == "true"

    # Create resource (service metadata)
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "2.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add Jaeger exporter if configured
    if jaeger_host:
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

    # Add console exporter for debugging
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set global tracer provider
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "dataset-analyzer") -> trace.Tracer:
    """
    Get tracer for manual span creation.

    Usage:
        tracer = get_tracer("my-component")
        with tracer.start_as_current_span("operation-name"):
            # Your code here
            pass
    """
    return trace.get_tracer(name)


def instrument_fastapi(app) -> None:
    """
    Automatically instrument FastAPI application.

    This adds automatic tracing to all HTTP endpoints.
    Call after creating FastAPI app:

        app = FastAPI()
        instrument_fastapi(app)
    """
    FastAPIInstrumentor.instrument_app(app)
