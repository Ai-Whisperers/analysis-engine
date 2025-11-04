# Portability Enhancement Report

## Executive Summary
- The project already offers a layered Spark-centric ingestion and sentiment analysis stack, but it assumes Linux/x86 Docker deployments, Oracle Cloud shape defaults, and local file paths for several workflows. These assumptions reduce its portability as a general Spark extension.
- Key portability friction points include Unix-only tooling in developer workflows, platform-specific Python dependencies, hard-coded local storage assumptions within Spark phases, and Oracle-specific deployment scripts.
- The recommendations below prioritize separating Spark-ready libraries from service code, introducing conditional/extra dependencies, abstracting file systems and paths, and expanding packaging and deployment artifacts so the stack can run on managed Spark services and varied infrastructure.

## Current Portability Constraints
- Developer automation uses POSIX-only commands (e.g., `find` and `rm` in `Makefile:39-43`), preventing native Windows workflows without WSL.
- Runtime dependencies include Unix-only packages such as `uvloop` (`pyproject.toml:23-24`) and CPU-specific wheels like `faiss-cpu` (`pyproject.toml:40`), which break installation on Windows and many managed Spark clusters.
- Spark ingestion orchestrates its own `SparkSession` internally (`parquet-conversion-and-fields-mapping/pipeline/ingest_pipeline.py:56`), limiting reuse in existing Spark jobs and preventing submission to remote clusters that manage sessions.
- Semantic mapping and audit steps persist to the local filesystem (`parquet-conversion-and-fields-mapping/pipeline/semantic_map.py:131-136`), making the pipeline unsuitable for HDFS, S3, or DBFS-backed Spark environments without manual edits.
- The sentiment analyzer exposes only in-memory batch methods (`layers/sentiment_analyzer/analyzer.py:105`), so Spark users must write custom UDF wrappers for DataFrame usage.
- Containerization is tuned exclusively for Oracle Cloud Free Tier (`Dockerfile:2`, `deployment/setup-oracle-cloud.sh:2-126`), with no guidance for other clouds or multi-arch images.

## Recommendations

### Packaging & Distribution
- Split the core Spark utilities (schema profiling, semantic mapping, sentiment scoring) into a lightweight Python package (`dataset_analyzer_spark`) that can be zipped and shipped with `spark-submit --py-files`. Provide wheel builds alongside the current service package.
- Expose `setup.cfg`/`pyproject` entry points for Spark jobs (e.g., `dataset_analyzer.spark.ingest_cli:main`) to streamline use in Airflow, Databricks Jobs, or AWS Glue.
- Publish reproducible build artifacts in CI (wheel, source distribution, and zipped dependencies) to ease offline cluster deployments.
- Start the extraction with a minimal “library” module that re-exports today’s pipeline functions so existing imports keep working, then introduce breaking changes behind versioned namespaces once adoption starts.

### Spark Runtime Integration
- Accept an existing `SparkSession` throughout ingestion phases and add helper functions that register UDFs/UDAFs (e.g., `polars` preprocessing as Arrow-based `mapInPandas` and ONNX inference as vectorized Pandas UDF). This allows direct integration with DataFrame pipelines rather than forcing process-bound orchestration.
- Provide a `SentimentTransformer` class implementing the `pyspark.ml.Transformer` interface that wraps `SentimentAnalyzer` for column-level inference, enabling model persistence via Spark ML pipelines.
- Replace direct `print` logging in ingestion scripts with Spark-compatible logging and add task context support so the pipeline can run inside Spark Structured Streaming or notebook jobs.
- Ship a thin compatibility layer (`spark_runtime.shim`) that lets downstream teams keep calling `IngestionPipeline.run()` while internally delegating to the injected-session workflow, ensuring the refactor unblocks Spark portability without breaking local CLI tooling.

### Dependency Strategy
- Gate optional, platform-sensitive libraries behind extras (e.g., `pip install dataset-analyzer[sentiment,cpu]`) and runtime detection. Offer fallbacks (`asyncio` loop without `uvloop`, `faiss-cpu` replaced by `annoy`/`scann` on unsupported platforms) to keep base installs portable.
- Generate constraints files per platform/CPU architecture in CI to capture compatible versions and surface incompatibilities early.
- Document GPU-enabled alternatives (e.g., `onnxruntime-gpu`) and provide environment markers so Spark on Kubernetes or YARN with GPUs can leverage accelerated inference.

### Configuration & Storage Abstraction
- Extend `shared.config.Settings` to include URI-based storage targets (e.g., `DATA_URI`, `MODEL_URI`) with helpers for local paths vs. cloud object stores, allowing pipeline phases to use `fsspec` for multi-backend reads/writes.
- Parameterize the staging/audit output locations to support HDFS/S3/DBFS, and refactor `save_unmapped_for_learning` to use the same abstraction rather than hard-coded `staging/` directories.
- Externalize canonical schema files through configuration or catalog integration (e.g., fetch from AWS Glue Data Catalog or Delta table) instead of assuming local YAMLs.

### Containerization & Deployment
- Produce a multi-arch base image (linux/amd64 and linux/arm64) with build arguments for CPU/GPU ONNX runtimes, and loosen the baked-in Oracle tuning so images suit AKS, EKS, Databricks, or EMR.
- Replace the Oracle-specific shell installer with infrastructure-agnostic Terraform/Ansible modules and document Helm charts or Kustomize overlays so the stack can be deployed alongside Spark on Kubernetes.
- Add lightweight images for Spark-executor sidecars that host the ONNX model cache and REST API for inference, enabling cluster-wide reuse without large broadcast variables.

### Developer Workflow & Testing
- Provide cross-platform tooling by replacing POSIX shell commands with Python scripts (`python -m tasks.clean`) and supporting `tox` or `nox` for environment management.
- Add integration tests that run the ingestion pipeline against mocked object stores (e.g., `s3fs`, `adlfs`) and Spark local/remote clusters to verify portability.
- Include Databricks/EMR job definitions or GitHub Actions matrix jobs that run `spark-submit` against multiple Spark versions to ensure forward compatibility.

## Immediate Sprint Focus
- Package the Spark-specific utilities into `dataset_analyzer_spark`, publish a wheel/zip artifact from CI, and document `spark-submit --py-files dist/dataset_analyzer_spark-*.zip` usage so cluster teams can test integration quickly.
- Refactor ingestion entry points to accept an injected `SparkSession`, adopt Spark logging APIs, and expose a temporary adapter that preserves the CLI contract while enabling remote Spark job submission.

## Backlog Tickets (Sprint-Ready)
1. **DAT-PORT-001 – Spark Distribution Package**
   - Scope: Extract the ingestion/semantic mapping/sentiment helpers into `dataset_analyzer_spark`, add `pyproject` entry points, generate wheel + zip artifacts in CI, and publish usage docs for `spark-submit --py-files`.
   - Outcome: Cluster teams can install or attach the packaged utilities without cloning the monorepo, unblocking external Spark workloads.
2. **DAT-PORT-002 – SparkSession Injection Refactor**
   - Scope: Update ingestion phases to accept pre-created `SparkSession` instances, migrate logging to Spark loggers, and implement the temporary shim that keeps `IngestionPipeline.run()` compatible with the CLI.
   - Outcome: The pipeline runs seamlessly on managed Spark services while preserving current operator workflows.

## Suggested Roadmap
1. **Short Term (1-2 sprints)**: Factor out the Spark-ready library package, refactor ingestion to accept injected `SparkSession` instances (with compatibility shim), add optional dependency gates, and replace Unix-only developer commands.
2. **Mid Term (3-5 sprints)**: Deliver Spark ML transformers/UDF helpers, storage abstraction via `fsspec`, and multi-arch Docker builds with generalized deployment automation.
3. **Long Term (6+ sprints)**: Harden managed Spark integrations (job templates, Terraform modules), publish artifacts to internal registries, and add GPU-aware deployment paths for sentiment inference at scale.

