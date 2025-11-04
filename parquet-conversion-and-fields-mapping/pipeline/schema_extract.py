"""Phase 2: Schema Extraction & Versioning."""
import json
import os
from datetime import datetime
from pyspark.sql import DataFrame
from typing import Dict, List, Any


def generate_schema_version() -> str:
    """Generate schema version timestamp."""
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def extract_schema(df: DataFrame, source_path: str, version: str = None) -> Dict[str, Any]:
    """Extract schema from DataFrame."""
    if version is None:
        version = generate_schema_version()

    schema_fields = [f.name for f in df.schema.fields]

    schema_record = {
        "version": version,
        "source_path": source_path,
        "fields": schema_fields,
        "field_count": len(schema_fields),
        "extracted_at": datetime.utcnow().isoformat(),
    }

    return schema_record


def extract_inferred_schema(spark, path: str, fmt: str, read_opts: Dict[str, str] = None) -> str:
    """Extract inferred schema (for future type casting reference)."""
    default_opts = {
        "header": "true",
        "inferSchema": "true",  # Enable inference
        "multiLine": "true",
        "quote": '"',
        "escape": '"',
        "mode": "PERMISSIVE"
    }

    if read_opts:
        default_opts.update(read_opts)

    df_inferred = spark.read.format(fmt).options(**default_opts).load(path)
    return df_inferred.schema.json()


def save_schema(schema_record: Dict[str, Any], output_dir: str = "output/audit_logs"):
    """Save schema record to JSON file."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"schema_{schema_record['version']}.json")

    with open(output_path, 'w') as f:
        json.dump(schema_record, f, indent=2)

    return output_path


def detect_schema_drift(current_fields: List[str], previous_schema_path: str = None) -> Dict[str, Any]:
    """Detect schema drift compared to previous schema."""
    if not previous_schema_path or not os.path.exists(previous_schema_path):
        return {"drift_detected": False, "changes": None}

    with open(previous_schema_path, 'r') as f:
        previous_schema = json.load(f)
        previous_fields = set(previous_schema.get('fields', []))

    current_fields_set = set(current_fields)

    added = list(current_fields_set - previous_fields)
    removed = list(previous_fields - current_fields_set)
    renamed = []  # Could implement fuzzy matching here

    drift = {
        "drift_detected": len(added) > 0 or len(removed) > 0,
        "changes": {
            "added": added,
            "removed": removed,
            "renamed": renamed,
        }
    }

    return drift


if __name__ == "__main__":
    import sys
    from ingest_raw import create_spark_session, read_raw_data

    if len(sys.argv) < 2:
        print("Usage: python schema_extract.py <file_path> [format]")
        sys.exit(1)

    path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"

    spark = create_spark_session()
    df = read_raw_data(spark, path, fmt)

    # Extract schema
    schema_record = extract_schema(df, path)
    print(json.dumps(schema_record, indent=2))

    # Save schema
    saved_path = save_schema(schema_record)
    print(f"\nSchema saved to: {saved_path}")
