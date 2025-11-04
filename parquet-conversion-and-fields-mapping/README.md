# Spark Ingestion Pipeline V2

Production-ready two-phase ingestion pattern that decouples schema extraction from data ingestion, adds self-learning semantic mapping, and produces a verifiable audit trail.

 Architecture

## Input path: 
ingest_cli.py (via --path arg) → ingest_pipeline.py
(source_path param) → passed to read_raw_data() in ingest_raw.py

## Output path: 
ingest_cli.py (via --output arg, default:
output/cleaned_data) → ingest_pipeline.py (output_path param) → passed to
persist_parquet()/persist_delta() in persist_data.py


### Pipeline Phases

- **Phase 0**: Input Profiling - Detect format/encoding, validate integrity
- **Phase 1**: Raw Read - Load all columns as strings (no type inference)
- **Phase 2**: Schema Extraction & Versioning - Persist header/shape separately
- **Phase 3**: Semantic Mapping - Normalize headers and map to canonical schema
- **Phase 4**: Persist - Write to Parquet/Delta with optimal layout
- **Phase 5**: Validation & Audit Trail - Generate verifiable audit records

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### CLI

```bash
# Profile a file
python ingest_cli.py profile --path data/input.csv --expect-header true --min-rows 1

# Run full pipeline
python ingest_cli.py run --path data/input.csv --fmt csv

# Use Delta Lake
python ingest_cli.py run --path data/input.csv --delta

# Custom output path
python ingest_cli.py run --path data/input.csv --output output/my_data
```

### Python API

```python
from pipeline.ingest_pipeline import run_pipeline

results = run_pipeline(
    source_path="data/input.csv",
    fmt="csv",
    output_path="output/cleaned_data",
    use_delta=False
)
```

## Directory Structure

```
/
├── pipeline/
│   ├── profile_input.py       # Phase 0: Profiling
│   ├── ingest_raw.py          # Phase 1: Raw read
│   ├── schema_extract.py      # Phase 2: Schema extraction
│   ├── semantic_map.py        # Phase 3: Semantic mapping
│   ├── persist_data.py        # Phase 4: Persistence
│   ├── validate_audit.py      # Phase 5: Validation
│   ├── ingest_pipeline.py     # Main orchestration
│   └── config/
│       ├── canonical_schema.yaml  # Canonical field mappings
│       └── spark.conf             # Spark configuration
├── output/
│   ├── cleaned_data/          # Parquet/Delta output
│   ├── audit_logs/            # Audit records
│   └── quarantine/            # Malformed rows
├── staging/
│   └── new_headers.json       # Unmapped headers for learning
├── ingest_cli.py              # CLI interface
└── requirements.txt
```

## Configuration

### Canonical Schema Mapping

Edit `pipeline/config/canonical_schema.yaml` to define canonical field mappings:

```yaml
user_id: [userid, id, user id, uid]
nps: [nps, net promoter score, promoter_score]
email: [mail, email address, e-mail]
timestamp: [time, date, created_at, datetime]
```

### Spark Configuration

Edit `pipeline/config/spark.conf` for Spark settings:

```ini
spark.sql.shuffle.partitions=24
spark.sql.caseSensitive=false
spark.sql.parquet.compression.codec=snappy
```

## Features

- **Format Detection**: Auto-detect CSV, JSON formats and encoding
- **Schema Versioning**: Track schema evolution over time
- **Semantic Mapping**: Normalize and map headers to canonical schema
- **Fuzzy Matching**: Optional fuzzy matching for header mapping
- **Self-Learning**: Track unmapped headers for manual review
- **Audit Trail**: Complete audit logs with content hashing
- **Data Validation**: Null checks, distinct counts, anomaly detection
- **Quarantine**: Isolate malformed rows
- **Drift Detection**: Track schema changes across runs

## Output

### Audit Record Example

```json
{
  "schema_version": "20250103120000",
  "source": "data/input.csv",
  "output": "output/cleaned_data",
  "rows": 10000,
  "columns": 5,
  "nulls": {"user_id": 0, "email": 5},
  "distincts": {"user_id": 9995, "email": 9995},
  "content_sha256": "abc123...",
  "validation": {
    "status": "passed",
    "alerts": []
  }
}
```

## License

MIT
