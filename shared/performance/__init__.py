"""
Shared performance library for 10x speed improvements.

Provides:
- Polars data processing utilities (10x faster than pandas)
- ONNX INT8 model inference (4x faster than HuggingFace)
- Data quality utilities (boolean normalization, date parsing)
- Schema detection and validation
"""

from .polars_utils import (
    PolarsPreprocessor,
    normalize_boolean_fast,
    parse_date_flexible,
    detect_schema,
)
from .onnx_utils import ONNXModelLoader, quantize_model

__all__ = [
    "PolarsPreprocessor",
    "normalize_boolean_fast",
    "parse_date_flexible",
    "detect_schema",
    "ONNXModelLoader",
    "quantize_model",
]
