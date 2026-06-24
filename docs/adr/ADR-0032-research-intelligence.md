# ADR-0032: Research Intelligence & Ensembles

## Context

In M14C, GQOS expanded the Alpha framework to handle massive-scale Research Intelligence. A single strategy is rarely sufficient for institutional capital allocation; models must be ensembled, market regimes must be identified, signals must be rigorously validated, and statistical edge decay (Feature Drift) must be detected. Additionally, millions of rows of forecast data needed high-performance serialization.

## Decision 1: Weighted Summation for Hierarchical Explanations

When blending models in the `StaticWeightEnsemble`, the final forecast explanation is computed as the weighted sum of both model-level contributions and feature-level contributions.

* **Rationale**: Traceability must survive the Ensemble process. If an ensemble outputs a score of `0.60`, the Portfolio Manager can drill down into the `ExplanationStore` to discover that `Model A` contributed `0.40` and `Model B` contributed `0.20`. Digging further, they can see exactly which features drove `Model A`'s contribution.

## Decision 2: Feature Drift via Telemetry

The `FeatureDriftDetector` employs statistical distribution checks (e.g., Mean Shift approximations) to compare Out-Of-Sample data against In-Sample baselines, but strictly emits `FeatureDriftDetectedEvent` telemetry rather than halting execution.

* **Rationale**: Edge decay in financial markets is often gradual. Crashing a live execution system or a massive Walk-Forward backtest because a feature drifted out of its 95% confidence bounds is overly aggressive. The telemetry approach enables automated strategy deprecation workflows (via downstream monitoring) without breaking the core engine.

## Decision 3: Conservative Quality Propagation

When ensembling forecasts, the overall `quality` score is defined as `min(quality_i)` across all contributing models.

* **Rationale**: An ensemble's integrity is bound by its weakest link. If Model A has perfect data quality (1.0), but Model B is utilizing corrupted or delayed data (0.2), the ensemble score cannot be trusted blindly. The minimum bound forces the optimizer to act conservatively when scaling position size for that specific bar.

## Decision 4: Parquet Serialization

The `ParquetForecastSerializer` was implemented utilizing `pyarrow` to store the dense `ForecastFrame`.

* **Rationale**: CSV serialization of numeric data at the tick/minute level across thousands of instruments consumes massive disk I/O and storage. Parquet provides columnar compression, drastically reducing the footprint of the `ExperimentRegistry` while allowing fast out-of-core reads for Machine Learning pipelines.

## Status

Approved and implemented in M14C.
