"""Phase 3: Semantic Mapping - Normalize headers and map to canonical schema."""
import re
import os
import json
import yaml
from typing import Dict, List, Tuple, Optional
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, lower, regexp_replace, trim

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


def load_canonical_schema(config_path: str = "pipeline/config/canonical_schema.yaml") -> Dict[str, List[str]]:
    """Load canonical schema mapping."""
    if not os.path.exists(config_path):
        return {}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def normalize_dataframe(df: DataFrame) -> Tuple[DataFrame, List[str], List[str]]:
    """Normalize column names: lowercase, trim, replace spaces with underscores."""
    orig_cols = df.columns

    # Create normalization expressions
    norm_exprs = [
        trim(lower(regexp_replace(col(c), r"\s+", "_"))).alias(c)
        for c in df.columns
    ]

    df_norm = df.select(*norm_exprs)
    norm_cols = [re.sub(r"\s+", "_", c.lower().strip()) for c in df.columns]

    # Rename columns to normalized versions
    for orig, norm in zip(orig_cols, norm_cols):
        df_norm = df_norm.withColumnRenamed(orig, norm)

    return df_norm, orig_cols, norm_cols


def alias_match(name: str, canonical: Dict[str, List[str]], threshold: int = 85) -> Optional[str]:
    """Match column name to canonical schema."""
    name_l = name.lower().strip()

    # Exact match or contains match first
    for target, aliases in canonical.items():
        # Check if target or any alias is in the name
        if target.lower() in name_l or name_l in target.lower():
            return target

        for alias in aliases:
            alias_l = alias.lower()
            if alias_l in name_l or name_l in alias_l:
                return target

    # Fuzzy match (optional)
    if FUZZY_AVAILABLE:
        best_target = None
        best_score = 0

        for target, aliases in canonical.items():
            for alias in aliases + [target]:
                score = fuzz.partial_ratio(name_l, alias.lower())
                if score > best_score:
                    best_score = score
                    best_target = target

        if best_score >= threshold:
            return best_target

    return None


def map_columns(norm_cols: List[str], canonical: Dict[str, List[str]],
                threshold: int = 85) -> Tuple[List[str], Dict[str, str], List[str]]:
    """Map normalized columns to canonical schema."""
    mapped_cols = []
    mapping_report = {}
    unmapped = []

    for c in norm_cols:
        target = alias_match(c, canonical, threshold)

        if target:
            mapped_cols.append(target)
            mapping_report[c] = target
        else:
            # Fallback: sanitize the original column name
            sanitized = re.sub(r"\W+", "_", c)
            mapped_cols.append(sanitized)
            unmapped.append(c)

    return mapped_cols, mapping_report, unmapped


def apply_semantic_mapping(df: DataFrame, canonical_path: str = "pipeline/config/canonical_schema.yaml",
                           threshold: int = 85) -> Tuple[DataFrame, Dict]:
    """Apply full semantic mapping pipeline."""

    # Load canonical schema
    canonical = load_canonical_schema(canonical_path)

    # Normalize
    df_norm, orig_cols, norm_cols = normalize_dataframe(df)

    # Map to canonical
    mapped_cols, mapping_report, unmapped = map_columns(norm_cols, canonical, threshold)

    # Rename columns
    df_mapped = df_norm.toDF(*mapped_cols)

    # Create report
    report = {
        "original_columns": orig_cols,
        "normalized_columns": norm_cols,
        "mapped_columns": mapped_cols,
        "mapping_report": mapping_report,
        "unmapped_columns": unmapped,
        "total_columns": len(orig_cols),
        "mapped_count": len(mapping_report),
        "unmapped_count": len(unmapped),
    }

    # Save unmapped for learning
    if unmapped:
        save_unmapped_for_learning(unmapped)

    return df_mapped, report


def save_unmapped_for_learning(unmapped: List[str], output_path: str = "staging/new_headers.json"):
    """Save unmapped headers for manual triage and learning."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Load existing unmapped headers
    existing = []
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            existing = json.load(f)

    # Append new unmapped headers
    for header in unmapped:
        if header not in existing:
            existing.append(header)

    # Save
    with open(output_path, 'w') as f:
        json.dump(existing, f, indent=2)


if __name__ == "__main__":
    import sys
    from ingest_raw import create_spark_session, read_raw_data

    if len(sys.argv) < 2:
        print("Usage: python semantic_map.py <file_path> [format]")
        sys.exit(1)

    path = sys.argv[1]
    fmt = sys.argv[2] if len(sys.argv) > 2 else "csv"

    spark = create_spark_session()
    df = read_raw_data(spark, path, fmt)

    # Apply semantic mapping
    df_mapped, report = apply_semantic_mapping(df)

    print(json.dumps(report, indent=2))
    print("\nMapped DataFrame:")
    df_mapped.show(5, truncate=False)
