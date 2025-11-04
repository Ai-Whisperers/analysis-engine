"""Phase 1: Raw Read - Load all columns as strings without type inference."""
from pyspark.sql import SparkSession, DataFrame
from typing import Dict


def create_spark_session(app_name: str = "RawIngestV2", config_path: str = None) -> SparkSession:
    """Create Spark session with configuration."""
    builder = (SparkSession.builder
        .appName(app_name)
        .config("spark.sql.files.ignoreCorruptFiles", "true")
        .config("spark.sql.caseSensitive", "false"))

    # Load additional config if provided
    if config_path:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    builder = builder.config(key.strip(), value.strip())

    return builder.getOrCreate()


def read_raw_data(spark: SparkSession, path: str, fmt: str = "csv",
                  read_opts: Dict[str, str] = None) -> DataFrame:
    """Read raw data with all columns as strings."""

    # Default options for CSV
    default_opts = {
        "header": "true",
        "inferSchema": "false",   # everything as string
        "multiLine": "true",
        "quote": '"',
        "escape": '"',
        "mode": "PERMISSIVE"      # keep bad rows; validate later
    }

    # Merge with user options
    if read_opts:
        default_opts.update(read_opts)

    # Read based on format
    if fmt.lower() == "csv":
        df_raw = spark.read.format("csv").options(**default_opts).load(path)
    elif fmt.lower() == "json":
        df_raw = spark.read.format("json").options(mode="PERMISSIVE").load(path)
    else:
        # Generic format (e.g., for Excel via external library)
        df_raw = spark.read.format(fmt).options(**default_opts).load(path)

    return df_raw


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ingest_raw.py <file_path> [format]")
        sys.exit(1)

    path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"

    spark = create_spark_session()
    df = read_raw_data(spark, path, fmt)

    print(f"Loaded {df.count()} rows with {len(df.columns)} columns")
    print("Schema:")
    df.printSchema()
    print("\nSample:")
    df.show(5, truncate=False)
