"""Main Orchestration Script - Execute all phases of ingestion pipeline."""
import os
import json
from typing import Dict, Any, Optional

# Import all phases
from profile_input import profile_file
from ingest_raw import create_spark_session, read_raw_data
from schema_extract import extract_schema, save_schema, detect_schema_drift, generate_schema_version
from semantic_map import apply_semantic_mapping
from persist_data import persist_parquet, persist_delta, quarantine_malformed_rows
from validate_audit import generate_audit_record, save_audit_record, validate_audit, generate_anomaly_report


class IngestionPipeline:
    """Orchestrates the complete ingestion pipeline."""

    def __init__(self, source_path: str, fmt: str = "csv",
                 output_path: str = "output/cleaned_data",
                 config_path: str = "pipeline/config/spark.conf",
                 use_delta: bool = False):
        self.source_path = source_path
        self.fmt = fmt
        self.output_path = output_path
        self.config_path = config_path
        self.use_delta = use_delta
        self.spark = None
        self.schema_version = None
        self.results = {}

    def run(self) -> Dict[str, Any]:
        """Execute all pipeline phases."""

        print("=" * 60)
        print("SPARK INGESTION PIPELINE V2")
        print("=" * 60)

        # Phase 0: Profile Input
        print("\n[Phase 0] Profiling input file...")
        try:
            profile = profile_file(self.source_path)
            self.results['profile'] = profile

            if not profile['validation']['passed']:
                raise ValueError(f"Profiling failed: {profile['validation']['errors']}")

            print(f"✓ Format: {profile['format']}")
            print(f"✓ Encoding: {profile['encoding']}")
            print(f"✓ Size: {profile['file_info']['size_mb']} MB")
        except Exception as e:
            print(f"✗ Profiling failed: {e}")
            raise

        # Initialize Spark
        print("\n[Initialization] Creating Spark session...")
        self.spark = create_spark_session(config_path=self.config_path)
        print("✓ Spark session created")

        # Phase 1: Raw Read
        print("\n[Phase 1] Reading raw data (all columns as strings)...")
        try:
            df_raw = read_raw_data(self.spark, self.source_path, self.fmt)
            row_count = df_raw.count()
            col_count = len(df_raw.columns)
            print(f"✓ Loaded {row_count} rows with {col_count} columns")
            self.results['raw_row_count'] = row_count
            self.results['raw_col_count'] = col_count
        except Exception as e:
            print(f"✗ Raw read failed: {e}")
            raise

        # Phase 2: Schema Extraction
        print("\n[Phase 2] Extracting schema...")
        try:
            self.schema_version = generate_schema_version()
            schema_record = extract_schema(df_raw, self.source_path, self.schema_version)
            schema_path = save_schema(schema_record)
            print(f"✓ Schema version: {self.schema_version}")
            print(f"✓ Schema saved to: {schema_path}")
            self.results['schema_version'] = self.schema_version
            self.results['schema_path'] = schema_path

            # Detect drift (if previous schema exists)
            # You would implement logic to find previous schema here
        except Exception as e:
            print(f"✗ Schema extraction failed: {e}")
            raise

        # Phase 3: Semantic Mapping
        print("\n[Phase 3] Applying semantic mapping...")
        try:
            df_mapped, mapping_report = apply_semantic_mapping(df_raw)
            print(f"✓ Mapped {mapping_report['mapped_count']} columns")
            print(f"✓ Unmapped {mapping_report['unmapped_count']} columns")
            if mapping_report['unmapped_columns']:
                print(f"  Unmapped: {', '.join(mapping_report['unmapped_columns'])}")
            self.results['mapping_report'] = mapping_report
        except Exception as e:
            print(f"✗ Semantic mapping failed: {e}")
            raise

        # Quarantine malformed rows
        print("\n[Quarantine] Checking for malformed rows...")
        try:
            quarantined = quarantine_malformed_rows(df_mapped)
            if quarantined > 0:
                print(f"⚠ Quarantined {quarantined} malformed rows")
            else:
                print("✓ No malformed rows detected")
            self.results['quarantined_rows'] = quarantined
        except Exception as e:
            print(f"✗ Quarantine check failed: {e}")

        # Phase 4: Persist
        print(f"\n[Phase 4] Persisting to {'Delta' if self.use_delta else 'Parquet'}...")
        try:
            if self.use_delta:
                result_path = persist_delta(df_mapped, self.output_path)
            else:
                result_path = persist_parquet(df_mapped, self.output_path)
            print(f"✓ Data persisted to: {result_path}")
            self.results['output_path'] = result_path
        except Exception as e:
            print(f"✗ Persistence failed: {e}")
            raise

        # Phase 5: Validation & Audit
        print("\n[Phase 5] Generating audit trail...")
        try:
            audit = generate_audit_record(
                df_mapped, self.schema_version,
                self.source_path, self.output_path,
                mapping_report
            )

            validation = validate_audit(audit)
            audit['validation'] = validation

            audit_path = save_audit_record(audit)
            print(f"✓ Audit saved to: {audit_path}")

            # Generate anomaly report
            anomaly_path = generate_anomaly_report(df_mapped)
            print(f"✓ Anomaly report saved to: {anomaly_path}")

            self.results['audit_path'] = audit_path
            self.results['validation'] = validation

            # Print validation status
            print(f"\nValidation Status: {validation['status'].upper()}")
            if validation['alerts']:
                for alert in validation['alerts']:
                    print(f"  {alert}")

        except Exception as e:
            print(f"✗ Validation/audit failed: {e}")
            raise

        # Summary
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Schema Version: {self.schema_version}")
        print(f"Rows Processed: {self.results['raw_row_count']}")
        print(f"Output: {self.output_path}")
        print(f"Audit: {self.results['audit_path']}")
        print("=" * 60)

        return self.results

    def cleanup(self):
        """Stop Spark session."""
        if self.spark:
            self.spark.stop()


def run_pipeline(source_path: str, fmt: str = "csv",
                output_path: str = "output/cleaned_data",
                use_delta: bool = False) -> Dict[str, Any]:
    """Run the complete ingestion pipeline."""

    pipeline = IngestionPipeline(
        source_path=source_path,
        fmt=fmt,
        output_path=output_path,
        use_delta=use_delta
    )

    try:
        results = pipeline.run()
        return results
    finally:
        pipeline.cleanup()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ingest_pipeline.py <file_path> [format] [output_path] [--delta]")
        sys.exit(1)

    source = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else "csv"
    output = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "output/cleaned_data"
    use_delta = "--delta" in sys.argv

    run_pipeline(source, fmt, output, use_delta)
