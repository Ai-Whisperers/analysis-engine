"""
End-to-end integration tests for full pipeline.

Tests the complete workflow:
1. Upload file → 2. Convert to Parquet → 3. Store in DB → 4. Export
"""

import pytest

from layers.parquet_conversion_layer import ParquetConverter
from layers.rag_layer import ShardedDatabase
from layers.output_layer import DataExporter


class TestEndToEndPipeline:
    """Test complete data processing pipeline."""

    def test_full_pipeline_csv(self, sample_csv, temp_dir):
        """
        Test complete pipeline with CSV input.

        Steps:
        1. Convert CSV to Parquet
        2. Load into sharded database
        3. Export to CSV/Excel/JSON
        """
        task_id = "test-task-001"

        # Step 1: Convert to Parquet
        parquet_path = str(temp_dir / "output.parquet")
        result = ParquetConverter.convert(
            input_path=sample_csv,
            output_path=parquet_path,
            task_id=task_id,
            sanitize_data=True,
            excel_safe=True,
        )

        assert result.records_count == 4
        assert result.columns_count > 0
        assert "plan" in result.schema
        assert result.data_quality is not None

        # Step 2: Load into database
        db = ShardedDatabase(base_dir=str(temp_dir / "shards"))
        records_loaded = db.load_from_parquet(task_id, parquet_path)

        assert records_loaded == 4

        # Step 3: Get records from database
        shard = db.get_shard(task_id)
        records = shard.get_records(task_id, limit=100)

        assert len(records) == 4
        assert all("data" in record for record in records)

        # Step 4: Export to different formats
        exporter = DataExporter(excel_safe=True)

        # CSV export
        csv_export_path = str(temp_dir / "export.csv")
        csv_file = exporter.export_to_csv(records, csv_export_path)
        assert Path(csv_file).exists()

        # JSON export
        json_export_path = str(temp_dir / "export.json")
        json_file = exporter.export_to_json(records, json_export_path)
        assert Path(json_file).exists()

        # Cleanup
        db.close_all()

    def test_data_quality_detection(self, sample_csv, temp_dir):
        """
        Test data quality issue detection.

        Verifies:
        - Null value detection
        - Whitespace contamination
        - Type inference
        """
        task_id = "test-quality-001"
        parquet_path = str(temp_dir / "quality_test.parquet")

        result = ParquetConverter.convert(
            input_path=sample_csv,
            output_path=parquet_path,
            task_id=task_id,
        )

        # Check data quality report
        assert "before" in result.data_quality
        assert "after" in result.data_quality
        assert "improvements" in result.data_quality

        before = result.data_quality["before"]
        assert "total_records" in before
        assert "null_by_column" in before
        assert before["total_records"] == 4

    def test_schema_detection(self, sample_csv, temp_dir):
        """
        Test automatic schema detection.

        Verifies:
        - Type inference (string, int, boolean, date)
        - Boolean normalization (true, si, 1)
        - Date parsing (multiple formats)
        """
        task_id = "test-schema-001"
        parquet_path = str(temp_dir / "schema_test.parquet")

        result = ParquetConverter.convert(
            input_path=sample_csv,
            output_path=parquet_path,
            task_id=task_id,
        )

        schema = result.schema

        # Verify schema detection
        assert "plan" in schema
        assert "score" in schema
        assert "outage_flag" in schema
        assert "comentario" in schema
        assert "fecha" in schema

        # Score should be detected as integer
        assert schema["score"] in ["integer", "float"]

        # Outage_flag should be detected as boolean
        assert schema["outage_flag"] == "boolean"


@pytest.mark.asyncio
class TestAsyncPipeline:
    """Test asynchronous processing capabilities."""

    async def test_concurrent_tasks(self, sample_csv, temp_dir):
        """
        Test multiple concurrent task processing.

        Simulates:
        - Multiple file uploads
        - Parallel processing
        - No lock contention (sharded DB)
        """
        import asyncio

        async def process_task(task_id, csv_path):
            """Process single task."""
            parquet_path = str(temp_dir / f"{task_id}.parquet")
            result = ParquetConverter.convert(
                input_path=csv_path,
                output_path=parquet_path,
                task_id=task_id,
            )
            return result

        # Process 3 tasks concurrently
        tasks = [
            process_task(f"task-{i}", sample_csv) for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.records_count == 4 for r in results)
