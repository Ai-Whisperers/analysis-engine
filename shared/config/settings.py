"""
Configuration settings from environment variables.

Uses pydantic for validation and type safety.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Environment variables:
    - ENVIRONMENT: dev, test, prod (default: dev)
    - LOG_LEVEL: DEBUG, INFO, WARNING, ERROR (default: INFO)
    - MAX_UPLOAD_SIZE: Maximum file size in MB (default: 100)
    - RATE_LIMIT_REQUESTS: Requests per minute (default: 100)
    - JAEGER_AGENT_HOST: Jaeger tracing host (optional)
    - API_KEY: API key for authentication (optional)
    """

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # File upload limits
    max_upload_size_mb: int = Field(default=100, alias="MAX_UPLOAD_SIZE_MB")

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(
        default=100, alias="RATE_LIMIT_REQUESTS_PER_MINUTE"
    )
    rate_limit_burst: int = Field(default=20, alias="RATE_LIMIT_BURST")

    # Security
    api_key: Optional[str] = Field(default=None, alias="API_KEY")
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")

    # Telemetry
    jaeger_agent_host: Optional[str] = Field(default=None, alias="JAEGER_AGENT_HOST")
    jaeger_agent_port: int = Field(default=6831, alias="JAEGER_AGENT_PORT")
    otel_console_export: bool = Field(default=False, alias="OTEL_CONSOLE_EXPORT")

    # Performance
    onnx_num_threads: Optional[int] = Field(default=None, alias="ONNX_NUM_THREADS")
    polars_num_threads: Optional[int] = Field(default=None, alias="POLARS_NUM_THREADS")

    # Paths
    models_dir: str = Field(default="models", alias="MODELS_DIR")
    data_dir: str = Field(default="data", alias="DATA_DIR")
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    This ensures settings are loaded only once and reused.

    Usage:
        from shared.config import get_settings

        settings = get_settings()
        print(settings.log_level)
    """
    return Settings()
