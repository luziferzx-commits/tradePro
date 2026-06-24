# ADR-0027: Research Dataset Versioning & Metadata Boundary

## Context

In M13A, GQOS required a mechanism to version datasets and define strategy experiments deterministically. A critical design question was whether the core research domain (`gqos.research`) should explicitly implement data loaders (e.g., `Pandas`, `PyArrow`, `Parquet`) to fetch historical prices.

## Decision 1: Pure Metadata Contract

We implemented `DatasetMetadata` as a pure dataclass containing only descriptive properties (`dataset_id`, `data_hash`, `schema_version`, `row_count`, `time_range`, `frequency`, `column_signature`). The core domain explicitly **does not** load or parse physical files.

* **Rationale**: Data loading is an Infrastructure / ETL concern. By decoupling the "Identity" of the dataset from the "Retrieval" of the dataset, GQOS remains lightweight. The research engine simply asserts that the `data_hash` of the data stream provided by an external ETL adapter perfectly matches the `data_hash` required by the `ExperimentDefinition`.

## Decision 2: Dataset Fingerprinting & Lineage

We introduced a `DatasetFingerprint` which combines the `data_hash`, `row_count`, `schema_version`, and `column_signature` into a secondary SHA-256 hash. Additionally, datasets can specify a `parent_dataset_id`.

* **Rationale**: Relying purely on a content hash is risky if schema definitions drift (e.g., a float32 column silently changes to float64 but the CSV hash remains similar, or column headers are reordered). The `Fingerprint` provides an impenetrable lock against schema drift and hash collisions. Lineage allows researchers to audit how aggregated datasets (e.g., 1-minute bars) were derived from their raw tick parents.

## Status

Approved and implemented in M13A.
