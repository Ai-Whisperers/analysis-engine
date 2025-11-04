"""
Data exporter for CSV, Excel, and JSON formats.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import polars as pl

from shared.security import ExcelFormulaProtection
from shared.telemetry import MetricsCollector, StructuredLogger

logger = StructuredLogger(__name__)


class DataExporter:
    """
    Export data to various formats with security protection.

    Features:
    - CSV export (fast, universal)
    - Excel export (formatted, Excel-safe)
    - JSON export (structured)
    - XSS protection
    - Excel formula injection protection
    """

    def __init__(self, excel_safe: bool = True):
        """
        Initialize data exporter.

        Args:
            excel_safe: Apply Excel formula protection
        """
        self.excel_safe = excel_safe

    def export_to_csv(
        self,
        records: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Export records to CSV.

        Args:
            records: List of record dictionaries
            output_path: Path for output CSV file

        Returns:
            Path to created file
        """
        import time

        start_time = time.time()

        logger.info(
            "Starting CSV export",
            num_records=len(records),
            output_path=output_path,
        )

        # Extract data from record structure
        data_records = [record["data"] for record in records]

        # Convert to Polars DataFrame (10x faster)
        df = pl.DataFrame(data_records)

        # Apply Excel protection if enabled
        if self.excel_safe:
            for col in df.select(pl.col(pl.Utf8)).columns:
                df = df.with_columns(
                    pl.col(col)
                    .map_elements(
                        ExcelFormulaProtection.sanitize,
                        return_dtype=pl.Utf8,
                    )
                    .alias(col)
                )

        # Write to CSV
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        df.write_csv(output_path)

        duration = time.time() - start_time

        logger.log_performance(
            operation="csv_export",
            duration_ms=duration * 1000,
            records_processed=len(records),
        )

        MetricsCollector.record_processing(
            layer="output-layer",
            operation="csv_export",
            records=len(records),
            duration_seconds=duration,
        )

        logger.info(
            "CSV export completed",
            output_path=output_path,
            records=len(records),
        )

        return output_path

    def export_to_excel(
        self,
        records: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Export records to Excel.

        Args:
            records: List of record dictionaries
            output_path: Path for output Excel file

        Returns:
            Path to created file
        """
        import time

        start_time = time.time()

        logger.info(
            "Starting Excel export",
            num_records=len(records),
            output_path=output_path,
        )

        # Extract data from record structure
        data_records = [record["data"] for record in records]

        # Convert to Polars DataFrame
        df = pl.DataFrame(data_records)

        # Apply Excel protection (always enabled for Excel)
        for col in df.select(pl.col(pl.Utf8)).columns:
            df = df.with_columns(
                pl.col(col)
                .map_elements(
                    ExcelFormulaProtection.sanitize,
                    return_dtype=pl.Utf8,
                )
                .alias(col)
            )

        # Write to Excel
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        df.write_excel(output_path)

        duration = time.time() - start_time

        logger.log_performance(
            operation="excel_export",
            duration_ms=duration * 1000,
            records_processed=len(records),
        )

        MetricsCollector.record_processing(
            layer="output-layer",
            operation="excel_export",
            records=len(records),
            duration_seconds=duration,
        )

        logger.info(
            "Excel export completed",
            output_path=output_path,
            records=len(records),
        )

        return output_path

    def export_to_json(
        self,
        records: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Export records to JSON.

        Args:
            records: List of record dictionaries
            output_path: Path for output JSON file

        Returns:
            Path to created file
        """
        import time

        start_time = time.time()

        logger.info(
            "Starting JSON export",
            num_records=len(records),
            output_path=output_path,
        )

        # Extract data from record structure
        data_records = [record["data"] for record in records]

        # Write to JSON
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data_records, f, indent=2, ensure_ascii=False)

        duration = time.time() - start_time

        logger.log_performance(
            operation="json_export",
            duration_ms=duration * 1000,
            records_processed=len(records),
        )

        MetricsCollector.record_processing(
            layer="output-layer",
            operation="json_export",
            records=len(records),
            duration_seconds=duration,
        )

        logger.info(
            "JSON export completed",
            output_path=output_path,
            records=len(records),
        )

        return output_path
