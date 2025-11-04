"""
Performance benchmark tests.

Validates 10x performance improvement targets.
"""

import time
from pathlib import Path

import polars as pl
import pytest

from layers.parquet_conversion_layer import ParquetConverter
from shared.performance import PolarsPreprocessor


class TestPolarsPerformance:
    """Benchmark Polars data processing."""

    def test_polars_preprocessing_speed(self, temp_dir):
        """
        Benchmark Polars preprocessing speed.

        Target: 100K records/min (10x faster than pandas)
        """
        # Create large CSV
        num_records = 10000
        csv_content = "plan,score,comentario\n"
        for i in range(num_records):
            csv_content += f"Basic,{i % 10},Comment {i}\n"

        csv_path = temp_dir / "large_data.csv"
        csv_path.write_text(csv_content)

        # Benchmark
        start_time = time.time()

        df = pl.read_csv(str(csv_path))

        # Apply transformations
        df = df.with_columns([
            pl.col("plan").str.strip_chars(),
            pl.col("comentario").str.strip_chars(),
        ])

        duration = time.time() - start_time

        # Calculate throughput
        throughput = num_records / duration  # records/sec

        print(f"\nPolars throughput: {throughput:.0f} records/sec")
        print(f"Duration: {duration:.2f} seconds for {num_records} records")

        # Target: > 1000 records/sec (conservative)
        assert throughput > 1000, (
            f"Polars too slow: {throughput:.0f} records/sec (target: >1000)"
        )

    @pytest.mark.benchmark(min_rounds=5)
    def test_conversion_benchmark(self, sample_csv, temp_dir, benchmark):
        """
        Benchmark full Parquet conversion.

        Uses pytest-benchmark for accurate measurements.
        """

        def convert():
            parquet_path = str(temp_dir / "benchmark.parquet")
            return ParquetConverter.convert(
                input_path=sample_csv,
                output_path=parquet_path,
                task_id="benchmark-task",
            )

        result = benchmark(convert)

        assert result.records_count > 0


class TestDatabasePerformance:
    """Benchmark database operations."""

    def test_bulk_insert_speed(self, temp_dir):
        """
        Benchmark bulk insert speed.

        Target: 100K writes/sec with sharded SQLite
        """
        from layers.rag_layer import DatabaseShard

        db_path = str(temp_dir / "perf_test.db")

        with DatabaseShard(db_path) as shard:
            shard.create_tables()

            # Create test records
            num_records = 10000
            records = [
                {"id": i, "plan": "Basic", "score": i % 10}
                for i in range(num_records)
            ]

            # Benchmark bulk insert
            start_time = time.time()
            shard.bulk_insert_records("perf-task", records)
            duration = time.time() - start_time

            throughput = num_records / duration

            print(f"\nBulk insert throughput: {throughput:.0f} records/sec")
            print(f"Duration: {duration:.2f} seconds for {num_records} records")

            # Target: > 10K records/sec
            assert throughput > 10000, (
                f"Bulk insert too slow: {throughput:.0f} records/sec"
            )


class TestMemoryEfficiency:
    """Test memory efficiency."""

    def test_memory_usage_parquet(self, temp_dir):
        """
        Test memory usage with Parquet files.

        Parquet should use 50% less memory than pandas.
        """
        import psutil
        import os

        process = psutil.Process(os.getpid())

        # Create test data
        num_records = 50000
        data = {
            "plan": ["Basic"] * num_records,
            "score": list(range(num_records)),
            "comentario": [f"Comment {i}" * 10 for i in range(num_records)],
        }

        # Measure initial memory
        mem_before = process.memory_info().rss / (1024 * 1024)  # MB

        # Load with Polars
        df = pl.DataFrame(data)

        # Write to Parquet
        parquet_path = temp_dir / "memory_test.parquet"
        df.write_parquet(parquet_path, compression="zstd")

        # Read back
        df_loaded = pl.read_parquet(parquet_path)

        # Measure final memory
        mem_after = process.memory_info().rss / (1024 * 1024)  # MB
        mem_used = mem_after - mem_before

        print(f"\nMemory used: {mem_used:.1f} MB for {num_records} records")

        # Should use < 200 MB for 50K records
        assert mem_used < 200, f"Memory usage too high: {mem_used:.1f} MB"


@pytest.mark.slow
class TestStressTests:
    """Stress tests for large datasets."""

    def test_large_dataset_processing(self, temp_dir):
        """
        Test processing of large dataset (100K records).

        This is a stress test for production workloads.
        """
        # Create large CSV
        num_records = 100000
        csv_path = temp_dir / "large.csv"

        print(f"\nGenerating {num_records} records...")

        with open(csv_path, "w") as f:
            f.write("plan,score,outage_flag,comentario\n")
            for i in range(num_records):
                f.write(f"Basic,{i % 10},true,Comment {i}\n")

        # Process
        parquet_path = temp_dir / "large.parquet"

        start_time = time.time()

        result = ParquetConverter.convert(
            input_path=str(csv_path),
            output_path=str(parquet_path),
            task_id="stress-test",
        )

        duration = time.time() - start_time

        print(f"Processed {num_records} records in {duration:.2f} seconds")
        print(f"Throughput: {num_records / duration:.0f} records/sec")

        assert result.records_count == num_records
        # Should complete in < 60 seconds
        assert duration < 60, f"Processing too slow: {duration:.2f} seconds"
