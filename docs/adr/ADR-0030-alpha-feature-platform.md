# ADR-0030: Alpha Feature Platform & DAG Execution

## Context

In M14A, GQOS initiated the `gqos.alpha` domain to handle the systematic computation of predictive features (indicators) used by the Alpha models. A core challenge in institutional research is managing hundreds of features efficiently. Re-calculating nested features (e.g., ADX requiring True Range) for every strategy leads to immense computational waste.

## Decision 1: Directed Acyclic Graph (DAG) Resolution

We implemented an automatic Topological Sort via Kahn's Algorithm inside the `FeatureStore`. 

* **Rationale**: Researchers should not be burdened with manually ordering their feature computation arrays. By simply returning a list of `feature_id` strings from the `dependencies()` method, the `FeatureStore` dynamically calculates the optimal execution order, detects missing features, and proactively traps circular dependencies via `FeatureDependencyCycleError`.

## Decision 2: In-Memory Feature Caching

We introduced an `ICache` interface with an initial `InMemoryCache` implementation. The cache keys strictly combine the `dataset_hash` with the `FeatureMetadata.calculate_hash()` and `feature_id`.

* **Rationale**: If fifty Alpha models require `RSI_14`, the system calculates it once and caches the `pandas.Series`. Submitting subsequent models retrieves the array instantaneously. The interface approach allows us to easily drop in a `ParquetDiskCache` or `RedisCache` in M14+ without refactoring the core engine.

## Decision 3: The Pandas/Numpy Boundary

For the first time in the GQOS core, `pandas` and `numpy` were explicitly allowed inside `gqos.alpha`.

* **Rationale**: Vectorized math is strictly mandatory for Alpha generation at scale. However, this dependency is strictly constrained to the `alpha` (and subsequently `backtest`) domains. `gqos.portfolio`, `gqos.risk`, and `gqos.accounting` remain purely scalar/domain-driven to ensure precision and determinism.

## Status

Approved and implemented in M14A.
