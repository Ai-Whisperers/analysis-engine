"""
Output layer - API endpoints for results and exports.

Responsibilities:
- Serve analysis results via API
- Export to CSV, Excel, JSON
- Semantic search endpoint
- Data visualization endpoints
"""

from .app import app, create_app
from .exporter import DataExporter

__all__ = ["app", "create_app", "DataExporter"]
