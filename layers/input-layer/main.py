"""
Entry point for input layer service.

Run with:
    uvicorn layers.input-layer.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from .app import app

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "layers.input-layer.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only
        log_level="info",
    )
