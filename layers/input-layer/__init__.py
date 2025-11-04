"""
Input layer - FastAPI endpoints for file uploads and validation.

Responsibilities:
- Accept CSV/Excel/Parquet uploads
- Validate file format and size
- Rate limiting and security checks
- Return task_id for async processing
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
