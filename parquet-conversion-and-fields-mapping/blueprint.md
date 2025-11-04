# Spark Ingestion Plan — v2 (Production‑Ready)

> A hardened, auditable two‑phase ingestion pattern that **decouples schema extraction from data ingestion**, adds **self‑learning semantic mapping**, and produces a **verifiable audit trail** ready for orchestration.

---

## Phase 0 — Input Profiling (pre‑Spark)
**Goal:** detect format/encoding, validate basic integrity before cluster work.

- Detect MIME/encoding (e.g., `python-magic`, `chardet`).
- Sanity checks: file size, row count sample, header presence, delimiter heuristics.
- Fail‑fast: reject empty files, mixed encodings, or header/row length mismatch.

**CLI stub**
```bash
ingest profile --path <infile> --expect-header true --min-rows 1
```

---

## Phase 1 — Raw Read (all columns as string)
**Goal:** load without type inference to preserve raw fidelity.

```python
from pyspark.sql import SparkSession
spark = (SparkSession.builder
    .appName("RawIngestV2")
    .config("spark.sql.files.ignoreCorruptFiles", "true")
    .config("spark.sql.caseSensitive", "false")
    .getOrCreate())

fmt = "csv"                 # or "json" / "com.crealytics.spark.excel"
path = "data/input.csv"

read_opts = {
    "header": "true",
    "inferSchema": "false",   # everything as string
    "multiLine": "true",
    "quote": '"',
    "escape": '"',
    "mode": "PERMISSIVE"      # keep bad rows; validate later
}

df_raw = spark.read.format(fmt).options(**read_opts).load(path)
```

---

## Phase 2 — Schema Extraction & Versioning
**Goal:** persist header/shape separately from data.

```python
from datetime import datetime
schema_fields = [f.name for f in df_raw.schema.fields]
SCHEMA_VERSION = datetime.utcnow().strftime("%Y%m%d%H%M%S")

schema_record = {
    "version": SCHEMA_VERSION,
    "source_path": path,
    "fields": schema_fields,
}
# persist to JSON/Delta/SQLite – chosen in config
```

Optionally compute an *inferred* schema for later casting (never used to read raw):
```python
df_inferred = (spark.read.format(fmt)
    .options({**read_opts, "inferSchema": "true"})
    .load(path))
SCHEMA_INFERRED_JSON = df_inferred.schema.json()
```

---

## Phase 3 — Semantic Mapping (normalization → aliases → fuzzy → embeddings)
**Goal:** normalize headers and map them to canonical targets with a deterministic, reviewable chain.

### 3.1 Normalize
```python
import re
from pyspark.sql.functions import col, lower, regexp_replace, trim

norm = [ trim(lower(regexp_replace(col(c), r"\s+", "_"))).alias(c) for c in df_raw.columns ]
df_norm = df_raw.select(*norm)
orig_cols = df_raw.columns
norm_cols = df_norm.columns
```

### 3.2 Alias table (canonical map)
- Stored in `config/canonical_schema.yaml` (versioned).
- Example:
```yaml
# config/canonical_schema.yaml
user_id: [userid, id, user id, uid]
nps: [nps, net promoter score, promoter_score, satisfaction]
email: [mail, email address, e-mail]
timestamp: [time, date, created_at, datetime]
```

### 3.3 Deterministic remap (+ optional fuzzy)
```python
from typing import List, Dict
from rapidfuzz import fuzz

def alias_match(name: str, canonical: Dict[str, List[str]], threshold: int = 85):
    name_l = name.lower()
    # exact/contains first
    for target, aliases in canonical.items():
        if any(a in name_l for a in aliases + [target]):
            return target
    # fuzzy (optional)
    best = max(((target, max(fuzz.partial_ratio(name_l, a) for a in aliases))
               for target, aliases in canonical.items()), key=lambda x: x[1], default=(None,0))
    return best[0] if best[1] >= threshold else None

mapped = []
for c in norm_cols:
    t = alias_match(c, CANONICAL_MAP)
    mapped.append(t if t else re.sub(r"\W+", "_", c))

df_mapped = df_norm.toDF(*mapped)
```

### 3.4 Embedding fallback (optional, for long‑tail)
- Build small header‑phrase embeddings (MiniLM/all‑MiniLM‑L6‑v2) for canonical keys + incoming headers.
- Pick top‑1 cosine if score ≥ configurable threshold (e.g., 0.78) and log the suggestion as *pending*.
- **Never auto‑promote** embedding matches; require approval.

### 3.5 Learning loop
- Unmapped/low‑confidence headers are appended to `staging/new_headers.json` for manual triage.
- Approved mappings are merged into `canonical_schema.yaml` with a new schema version.

---

## Phase 4 — Persist (Parquet/Delta) with layout & compression
**Goal:** write clean, uniform data for downstream compute.

```python
TARGET_SIZE_MB = 128
num_partitions = max(1, int(df_mapped.storageLevel.useMemory and df_mapped.rdd.getNumPartitions()))

(df_mapped
    .repartition(num_partitions)
    .write
    .mode("overwrite")
    .option("compression", "snappy")
    .parquet("output/cleaned_data"))
```

**Notes**
- Prefer Delta Lake/Iceberg if you need ACID, time‑travel, and schema evolution.
- Keep all columns as **string** at this stage; cast downstream in curated tables.

---

## Phase 5 — Validation & Audit Trail
**Goal:** guarantee verifiability and quick forensics.

```python
from pyspark.sql.functions import count, countDistinct, col, lit
import hashlib, json, os

row_count = df_mapped.count()
nulls = {c: df_mapped.filter(col(c).isNull() | (col(c) == "")).count() for c in df_mapped.columns}
distincts = {c: df_mapped.select(countDistinct(c).alias("d")).first()["d"] for c in df_mapped.columns}

# dataset content hash – stable ordering via collect list of row hashes (for small/medium batches)
content_hash = hashlib.sha256("\n".join(sorted(df_mapped.rdd.map(lambda r: json.dumps(r.asDict(), sort_keys=True)).collect())).encode()).hexdigest()

audit = {
    "schema_version": SCHEMA_VERSION,
    "source": path,
    "output": "output/cleaned_data",
    "rows": row_count,
    "nulls": nulls,
    "distincts": distincts,
    "content_sha256": content_hash,
}
os.makedirs("output/audit_logs", exist_ok=True)
with open(f"output/audit_logs/{SCHEMA_VERSION}.json", "w") as f:
    json.dump(audit, f, indent=2)
```

**Guardrails**
- If `rows==0` or `content_sha256` repeats unexpectedly → alert.
- If header disappears or type drift is detected repeatedly → alert.

---

## Error & Drift Handling
- Reader mode `PERMISSIVE` (ingest), flag and sample malformed rows to `output/quarantine/`.
- Track schema drift across runs; emit a drift report (added/removed/renamed fields).
- Simple anomaly panel: `df_mapped.describe()` snapshot saved to disk for operator review.

---

## Performance Tuning
- **File sizing:** coalesce/repartition to ~128 MB parquet files for HDFS/S3 efficiency.
- **Encoding:** `parquet.enable.dictionary=true`, `spark.sql.parquet.compression.codec=snappy`.
- **Shuffle:** set `spark.sql.shuffle.partitions` to cluster size (not default 200).
- **Pushdown:** keep columns narrow during Phase 3 (select only needed headers if known).

---

## Interfaces & Orchestration
- **FastAPI endpoint** `/ingest` → triggers Phases 0–5 with params `{path, fmt, source_id}`.
- **n8n**: call endpoint + fetch `audit.json` to route approvals (human‑in‑the‑loop for header learning).
- **CLI**
```bash
ingest run --path data/input.csv --fmt csv --delta false
```

---

## Directory Layout
```
/pipeline/
 ├── ingest_raw.py
 ├── schema_extract.py
 ├── semantic_map.py
 ├── validate_audit.py
 ├── config/
 │    ├── canonical_schema.yaml
 │    └── spark.conf
 └── output/
      ├── cleaned_data/
      ├── audit_logs/
      └── quarantine/
```

---

## Configuration (example `spark.conf`)
```ini
spark.sql.shuffle.partitions=24
spark.sql.caseSensitive=false
spark.sql.parquet.compression.codec=snappy
parquet.enable.dictionary=true
```

---

## Post‑Ingest (optional curated layer)
- Create a **curated** table that casts known columns to strong types.
- Enforce lightweight constraints (non‑empty `user_id`, timestamp parseable, `nps` in [0,10]).

```python
from pyspark.sql.types import IntegerType, TimestampType
from pyspark.sql.functions import to_timestamp

df_curated = (df_mapped
  .withColumn("nps", col("nps").cast(IntegerType()))
  .withColumn("timestamp", to_timestamp("timestamp"))
  .filter(col("user_id").isNotNull() & (col("user_id") != "")))
```

---

## Operational Checklist
- [ ] Phase 0 profile saved
- [ ] Schema version recorded
- [ ] Canonical map applied (+ pending suggestions staged)
- [ ] Parquet/Delta written with correct partitioning
- [ ] Audit JSON stored (+ content hash)
- [ ] Drift/anomaly report generated

---

### Notes
- Keep **semantic learning human‑approved**; automation suggests, operators decide.
- Treat this plan as a **living spec**: update `canonical_schema.yaml` and `spark.conf` alongside code changes.

