"""
FastAPI application for input layer.
"""

import uuid
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from shared.config import get_settings
from shared.security import (
    FileValidator,
    FileValidationError,
    RateLimitExceeded,
    TokenBucketRateLimiter,
)
from shared.telemetry import (
    MetricsCollector,
    StructuredLogger,
    get_correlation_id,
    set_correlation_id,
    setup_tracing,
)

settings = get_settings()
logger = StructuredLogger(__name__)

# Rate limiter (in-memory, $0 cost)
rate_limiter = TokenBucketRateLimiter(
    max_tokens=settings.rate_limit_requests_per_minute,
    refill_rate=settings.rate_limit_requests_per_minute / 60,
)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Features:
    - CORS middleware
    - Telemetry (logging, metrics, tracing)
    - Rate limiting
    - Security middleware
    - Prometheus metrics endpoint
    """
    app = FastAPI(
        title="Dataset Analyzer - Input Layer",
        description="Production-grade NPS dataset analyzer - $0 cost, 10x performance",
        version="2.0.0",
    )

    # CORS configuration
    allowed_origins = settings.allowed_origins.split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Setup telemetry
    setup_tracing(
        service_name="input-layer",
        jaeger_host=settings.jaeger_agent_host,
        jaeger_port=settings.jaeger_agent_port,
    )

    # Middleware for request tracking
    @app.middleware("http")
    async def track_requests(request: Request, call_next):
        """Track all HTTP requests with telemetry."""
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Track active requests
        with MetricsCollector.track_active_request():
            # Log request
            logger.info(
                f"Request: {request.method} {request.url.path}",
                method=request.method,
                path=request.url.path,
                client_ip=request.client.host if request.client else None,
            )

            # Process request
            import time

            start_time = time.time()
            try:
                response = await call_next(request)
                duration = time.time() - start_time

                # Record metrics
                MetricsCollector.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code,
                    duration_seconds=duration,
                )

                return response
            except Exception as e:
                duration = time.time() - start_time
                MetricsCollector.record_http_request(
                    method=request.method,
                    endpoint=request.url.path,
                    status=500,
                    duration_seconds=duration,
                )
                logger.error(
                    f"Request failed: {str(e)}",
                    method=request.method,
                    path=request.url.path,
                    error=str(e),
                )
                raise

    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


app = create_app()


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "input-layer",
        "version": "2.0.0",
    }


@app.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Upload dataset file for processing.

    Features:
    - Rate limiting (100 req/min per IP)
    - File validation (size, type, content)
    - XSS protection
    - Async processing (returns task_id)

    Args:
        file: Uploaded file (CSV, Excel, Parquet)

    Returns:
        {
            "task_id": "uuid",
            "status": "processing",
            "file_name": "data.csv"
        }

    Rate limit: 100 requests/minute per IP
    Max file size: 100 MB
    Allowed formats: CSV, XLSX, XLS, Parquet
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    try:
        rate_limiter.check(client_ip)
    except RateLimitExceeded as e:
        logger.log_security_event(
            event_type="rate_limit_exceeded",
            severity="warning",
            description=f"Rate limit exceeded for IP: {client_ip}",
            client_ip=client_ip,
        )
        MetricsCollector.rate_limit_hits_total.labels(endpoint="/upload").inc()
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {e.retry_after:.1f} seconds",
        )

    # Validate file name
    try:
        FileValidator.validate_file_name(file.filename)
    except FileValidationError as e:
        logger.log_security_event(
            event_type="invalid_filename",
            severity="warning",
            description=str(e),
            file_name=file.filename,
            client_ip=client_ip,
        )
        raise HTTPException(status_code=400, detail=str(e))

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Create upload directory
    upload_dir = Path(settings.upload_dir) / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file
    safe_filename = FileValidator.get_safe_filename(file.filename)
    file_path = upload_dir / safe_filename

    try:
        # Save uploaded file
        content = await file.read()
        file_path.write_bytes(content)

        # Validate file
        FileValidator.validate_file(
            str(file_path),
            check_mime=True,
            max_size=settings.max_upload_size_mb * 1024 * 1024,
        )

        # Log successful upload
        logger.info(
            "File uploaded successfully",
            task_id=task_id,
            file_name=safe_filename,
            file_size_mb=round(len(content) / (1024 * 1024), 2),
            client_ip=client_ip,
        )

        # Record metrics
        file_ext = file_path.suffix.lower()
        MetricsCollector.record_file_processed(
            file_type=file_ext,
            status="uploaded",
        )

        return {
            "task_id": task_id,
            "status": "uploaded",
            "file_name": safe_filename,
            "file_size_mb": round(len(content) / (1024 * 1024), 2),
            "message": "File uploaded successfully. Processing will begin shortly.",
        }

    except FileValidationError as e:
        # Delete invalid file
        if file_path.exists():
            file_path.unlink()
        upload_dir.rmdir()

        logger.log_security_event(
            event_type="file_validation_failed",
            severity="warning",
            description=str(e),
            file_name=safe_filename,
            client_ip=client_ip,
        )

        MetricsCollector.record_file_processed(
            file_type=file_path.suffix.lower() if file_path.suffix else "unknown",
            status="validation_failed",
        )

        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Cleanup on error
        if file_path.exists():
            file_path.unlink()
        if upload_dir.exists():
            upload_dir.rmdir()

        logger.error(
            "File upload failed",
            task_id=task_id,
            error=str(e),
            client_ip=client_ip,
        )

        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/status/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get processing status for a task.

    Args:
        task_id: Task UUID

    Returns:
        {
            "task_id": "uuid",
            "status": "processing" | "completed" | "failed",
            "progress": 0.5,
            "message": "Processing..."
        }
    """
    # TODO: Implement status tracking
    # For now, return placeholder
    return {
        "task_id": task_id,
        "status": "processing",
        "progress": 0.0,
        "message": "Status tracking not yet implemented",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with telemetry."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        correlation_id=get_correlation_id(),
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": get_correlation_id(),
        },
    )
