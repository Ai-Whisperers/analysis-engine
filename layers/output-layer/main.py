"""
Entry point for output layer service.

Run with:
    uvicorn layers.output-layer.main:app --host 0.0.0.0 --port 8001 --workers 4
"""

from .app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "layers.output-layer.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,  # Development only
        log_level="info",
    )
