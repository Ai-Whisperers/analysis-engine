"""Phase 5: Validation & Audit Trail - Generate verifiable audit records."""
import os
import json
import hashlib
from typing import Dict, Any
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, count, countDistinct, isnan, when


def compute_column_stats(df: DataFrame) -> Dict[str, Any]:
    """Compute statistics for each column."""
    stats = {
        "nulls": {},
        "distincts": {},
        "empty_strings": {},
    }

    for c in df.columns:
        # Null count
        null_count = df.filter(col(c).isNull()).count()
        stats["nulls"][c] = null_count

        # Empty string count
        empty_count = df.filter((col(c) == "")).count()
        stats["empty_strings"][c] = empty_count

        # Distinct count
        distinct_count = df.select(countDistinct(c).alias("d")).first()["d"]
        stats["distincts"][c] = distinct_count

    return stats


def compute_content_hash(df: DataFrame, sample_size: int = 10000) -> str:
    """
    Compute content hash for data verification.
    For large datasets, use sampling to avoid memory issues.
    """
    # Get row count
    total_rows = df.count()

    # Sample if dataset is large
    if total_rows > sample_size:
        sample_fraction = sample_size / total_rows
        df_sample = df.sample(False, sample_fraction, seed=42).limit(sample_size)
    else:
        df_sample = df

    # Collect rows and create hash
    rows = df_sample.rdd.map(lambda r: json.dumps(r.asDict(), sort_keys=True)).collect()
    content = "\n".join(sorted(rows))
    return hashlib.sha256(content.encode()).hexdigest()


def generate_audit_record(df: DataFrame, schema_version: str, source_path: str,
                         output_path: str, mapping_report: Dict = None) -> Dict[str, Any]:
    """Generate comprehensive audit record."""

    # Basic counts
    row_count = df.count()
    column_count = len(df.columns)

    # Column statistics
    stats = compute_column_stats(df)

    # Content hash
    content_hash = compute_content_hash(df)

    # Build audit record
    audit = {
        "schema_version": schema_version,
        "source": source_path,
        "output": output_path,
        "rows": row_count,
        "columns": column_count,
        "column_names": df.columns,
        "nulls": stats["nulls"],
        "empty_strings": stats["empty_strings"],
        "distincts": stats["distincts"],
        "content_sha256": content_hash,
    }

    # Add mapping report if provided
    if mapping_report:
        audit["mapping_report"] = mapping_report

    return audit


def save_audit_record(audit: Dict[str, Any], output_dir: str = "output/audit_logs") -> str:
    """Save audit record to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{audit['schema_version']}.json")

    with open(output_path, 'w') as f:
        json.dump(audit, f, indent=2)

    return output_path


def validate_audit(audit: Dict[str, Any]) -> Dict[str, Any]:
    """Validate audit record and generate alerts."""
    alerts = []
    status = "passed"

    # Check for zero rows
    if audit["rows"] == 0:
        alerts.append("CRITICAL: Zero rows in output")
        status = "failed"

    # Check for high null percentage
    total_cells = audit["rows"] * audit["columns"]
    total_nulls = sum(audit["nulls"].values())
    null_percentage = (total_nulls / total_cells * 100) if total_cells > 0 else 0

    if null_percentage > 50:
        alerts.append(f"WARNING: High null percentage: {null_percentage:.2f}%")
        status = "warning"

    # Check for unmapped columns
    if "mapping_report" in audit:
        unmapped_count = audit["mapping_report"].get("unmapped_count", 0)
        if unmapped_count > 0:
            alerts.append(f"INFO: {unmapped_count} columns not mapped to canonical schema")

    return {
        "status": status,
        "alerts": alerts,
        "null_percentage": null_percentage,
    }


def generate_anomaly_report(df: DataFrame, output_path: str = "output/audit_logs/anomaly_report.json"):
    """Generate anomaly report using describe()."""
    # Get describe statistics
    describe_df = df.describe()

    # Convert to dict
    stats_list = describe_df.collect()
    column_stats = {}

    for col_name in df.columns:
        column_stats[col_name] = {}

    for row in stats_list:
        metric = row["summary"]
        for col_name in df.columns:
            if col_name != "summary" and col_name in row.asDict():
                column_stats[col_name][metric] = row[col_name]

    # Save report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(column_stats, f, indent=2)

    return output_path


if __name__ == "__main__":
    import sys
    from ingest_raw import create_spark_session, read_raw_data
    from semantic_map import apply_semantic_mapping
    from schema_extract import generate_schema_version

    if len(sys.argv) < 2:
        print("Usage: python validate_audit.py <file_path> [format] [output_path]")
        sys.exit(1)

    path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"
    output_path = sys.argv[3] if len(sys.argv) > 3 else "output/cleaned_data"

    spark = create_spark_session()
    df = read_raw_data(spark, path, fmt)
    df_mapped, mapping_report = apply_semantic_mapping(df)

    # Generate audit
    schema_version = generate_schema_version()
    audit = generate_audit_record(df_mapped, schema_version, path, output_path, mapping_report)

    # Validate
    validation = validate_audit(audit)
    audit["validation"] = validation

    # Save audit
    audit_path = save_audit_record(audit)
    print(f"Audit saved to: {audit_path}")

    # Generate anomaly report
    anomaly_path = generate_anomaly_report(df_mapped)
    print(f"Anomaly report saved to: {anomaly_path}")

    print("\nValidation Results:")
    print(json.dumps(validation, indent=2))
