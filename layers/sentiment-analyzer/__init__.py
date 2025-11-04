"""
Sentiment analyzer - ONNX INT8 inference (4x faster than HuggingFace).

Responsibilities:
- Load ONNX INT8 quantized models
- Batch sentiment inference on CPU
- 4x faster than HuggingFace (60ms vs 250ms)
- 75% smaller models (30MB vs 120MB)
"""

from .analyzer import SentimentAnalyzer, SentimentResult

__all__ = ["SentimentAnalyzer", "SentimentResult"]
