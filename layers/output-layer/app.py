"""
FastAPI application for output layer.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from layers.rag_layer import ShardedDatabase
from shared.config import get_settings
from shared.telemetry import StructuredLogger, setup_tracing

from .exporter import DataExporter

settings = get_settings()
logger = StructuredLogger(__name__)

# Initialize database
db = ShardedDatabase()


class SearchRequest(BaseModel):
    """Search request model."""

    query: str
    task_id: str
    limit: int = 10


class ExportRequest(BaseModel):
    """Export request model."""

    task_id: str
    format: str  # "csv", "xlsx", "json"
    include_sentiment: bool = True
    excel_safe: bool = True


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Dataset Analyzer - Output Layer",
        description="Results API and export functionality",
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
        service_name="output-layer",
        jaeger_host=settings.jaeger_agent_host,
        jaeger_port=settings.jaeger_agent_port,
    )

    return app


app = create_app()


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "output-layer",
        "version": "2.0.0",
    }


@app.get("/results/{task_id}")
async def get_results(
    task_id: str,
    limit: int = Query(default=100, le=10000),
    offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:
    """
    Get analysis results for a task.

    Args:
        task_id: Task UUID
        limit: Maximum records to return (default: 100, max: 10000)
        offset: Offset for pagination

    Returns:
        {
            "task_id": "uuid",
            "total_records": 57023,
            "limit": 100,
            "offset": 0,
            "results": [...]
        }
    """
    try:
        shard = db.get_shard(task_id)

        # Get records with pagination
        # TODO: Implement proper pagination with LIMIT/OFFSET
        records = shard.get_records(task_id, limit=limit)

        logger.info(
            "Results retrieved",
            task_id=task_id,
            count=len(records),
        )

        return {
            "task_id": task_id,
            "total_records": len(records),  # TODO: Get actual count
            "limit": limit,
            "offset": offset,
            "results": records,
        }

    except Exception as e:
        logger.error(
            "Failed to retrieve results",
            task_id=task_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to retrieve results: {str(e)}")


@app.post("/search")
async def semantic_search(request: SearchRequest) -> Dict[str, Any]:
    """
    Semantic search using vector embeddings.

    Args:
        request: SearchRequest with query and task_id

    Returns:
        {
            "task_id": "uuid",
            "query": "text query",
            "results": [
                {"record_id": 123, "distance": 0.42, "text": "..."},
                ...
            ]
        }
    """
    # TODO: Implement semantic search with FAISS
    logger.info(
        "Semantic search requested",
        task_id=request.task_id,
        query=request.query,
    )

    return {
        "task_id": request.task_id,
        "query": request.query,
        "message": "Semantic search not yet implemented",
        "results": [],
    }


@app.post("/export")
async def export_results(request: ExportRequest) -> FileResponse:
    """
    Export results to CSV, Excel, or JSON.

    Args:
        request: ExportRequest with task_id and format

    Returns:
        File download response

    Formats:
        - csv: Comma-separated values
        - xlsx: Excel workbook
        - json: JSON array
    """
    try:
        # Get shard
        shard = db.get_shard(request.task_id)

        # Get all records
        records = shard.get_records(request.task_id, limit=1000000)

        if not records:
            raise HTTPException(status_code=404, detail="No results found for task")

        # Create exporter
        exporter = DataExporter(excel_safe=request.excel_safe)

        # Export based on format
        output_dir = Path(settings.data_dir) / "exports" / request.task_id
        output_dir.mkdir(parents=True, exist_ok=True)

        if request.format == "csv":
            file_path = exporter.export_to_csv(
                records=records,
                output_path=str(output_dir / f"{request.task_id}.csv"),
            )
            media_type = "text/csv"

        elif request.format == "xlsx":
            file_path = exporter.export_to_excel(
                records=records,
                output_path=str(output_dir / f"{request.task_id}.xlsx"),
            )
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        elif request.format == "json":
            file_path = exporter.export_to_json(
                records=records,
                output_path=str(output_dir / f"{request.task_id}.json"),
            )
            media_type = "application/json"

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {request.format}. Use: csv, xlsx, json",
            )

        logger.info(
            "Export completed",
            task_id=request.task_id,
            format=request.format,
            records=len(records),
            file_path=file_path,
        )

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=Path(file_path).name,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Export failed",
            task_id=request.task_id,
            format=request.format,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/statistics/{task_id}")
async def get_statistics(task_id: str) -> Dict[str, Any]:
    """
    Get aggregated statistics for a task.

    Args:
        task_id: Task UUID

    Returns:
        {
            "task_id": "uuid",
            "total_records": 57023,
            "sentiment_distribution": {
                "positive": 35000,
                "negative": 22023
            },
            "average_confidence": 0.87,
            ...
        }
    """
    # TODO: Implement statistics aggregation
    logger.info(
        "Statistics requested",
        task_id=task_id,
    )

    return {
        "task_id": task_id,
        "message": "Statistics not yet implemented",
    }
