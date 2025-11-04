"""Phase 4: Persist data to Parquet/Delta with optimal layout and compression."""
import os
from pyspark.sql import DataFrame
from typing import Optional


def calculate_partitions(df: DataFrame, target_size_mb: int = 128) -> int:
    """Calculate optimal number of partitions based on data size."""
    # Get current partitions
    current_partitions = df.rdd.getNumPartitions()

    # For production, you'd want to calculate based on actual data size
    # This is a simple heuristic
    return max(1, current_partitions)


def persist_parquet(df: DataFrame, output_path: str, target_size_mb: int = 128,
                   compression: str = "snappy", mode: str = "overwrite") -> str:
    """Persist DataFrame to Parquet with optimal settings."""

    # Calculate partitions
    num_partitions = calculate_partitions(df, target_size_mb)

    # Repartition for optimal file size
    df_repartitioned = df.repartition(num_partitions)

    # Write to parquet
    (df_repartitioned
        .write
        .mode(mode)
        .option("compression", compression)
        .parquet(output_path))

    return output_path


def persist_delta(df: DataFrame, output_path: str, target_size_mb: int = 128,
                 mode: str = "overwrite", partition_by: Optional[list] = None) -> str:
    """Persist DataFrame to Delta Lake format."""

    # Calculate partitions
    num_partitions = calculate_partitions(df, target_size_mb)

    # Repartition
    df_repartitioned = df.repartition(num_partitions)

    # Write to Delta
    writer = df_repartitioned.write.format("delta").mode(mode)

    if partition_by:
        writer = writer.partitionBy(*partition_by)

    writer.save(output_path)

    return output_path


def quarantine_malformed_rows(df: DataFrame, quarantine_path: str = "output/quarantine"):
    """Identify and quarantine malformed rows."""
    os.makedirs(quarantine_path, exist_ok=True)

    # In PERMISSIVE mode, corrupt records are placed in a _corrupt_record column
    if "_corrupt_record" in df.columns:
        corrupted = df.filter(df["_corrupt_record"].isNotNull())
        count = corrupted.count()

        if count > 0:
            corrupted.write.mode("overwrite").parquet(quarantine_path)
            return count

    return 0


if __name__ == "__main__":
    import sys
    from ingest_raw import create_spark_session, read_raw_data
    from semantic_map import apply_semantic_mapping

    if len(sys.argv) < 2:
        print("Usage: python persist_data.py <file_path> [format] [output_path]")
        sys.exit(1)

    path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "output/cleaned_data"

    spark = create_spark_session()
    df = read_raw_data(spark, path, fmt)
    df_mapped, _ = apply_semantic_mapping(df)

    # Quarantine malformed rows
    quarantined = quarantine_malformed_rows(df_mapped)
    if quarantined > 0:
        print(f"Quarantined {quarantined} malformed rows")

    # Persist to Parquet
    result_path = persist_parquet(df_mapped, output_path)
    print(f"Data persisted to: {result_path}")
    print(f"Row count: {df_mapped.count()}")
