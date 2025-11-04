"""
Parquet conversion layer - Convert uploaded files to optimized Parquet format.

Responsibilities:
- Load CSV/Excel files with Polars (10x faster)
- Detect and normalize schema
- Clean data (XSS protection, whitespace, dates, booleans)
- Convert to memory-mapped Parquet
- Generate data quality report
"""

from .converter import ParquetConverter, ConversionResult

__all__ = ["ParquetConverter", "ConversionResult"]
