# ADR-0031: Alpha Models & Explainability Architecture

## Context

In M14B, GQOS developed the contracts for generating actual trading Alpha (`IAlphaModel`). As an Institutional Quant Platform, GQOS cannot rely on black-box "Buy/Sell" signals. The system requires continuous probability forecasts, rigorous explainability, quality scores, and full lineage tracking from signal generation back to the raw dataset.

## Decision 1: The Forecast DataFrame vs Object Array

We decided that `IAlphaModel.generate_forecasts()` must return a `ForecastResult` containing a `ForecastFrame` (a `pandas.DataFrame`).

* **Rationale**: Vectorized math over millions of bars is required for walk-forward testing. An array of Python `Forecast` objects would be devastatingly slow. By wrapping the results in a DataFrame (`score`, `confidence`, `quality`, `horizon`, `forecast_id`), we maintain maximum throughput. 

## Decision 2: Separating Explanations from the DataFrame

We decided to keep `ForecastExplanation` inside a separate `ExplanationStore` rather than embedding a Python dictionary inside the `ForecastFrame`.

* **Rationale**: Pandas performs terribly when a column contains `object` types (like dicts). By keeping the DataFrame strictly float/string based and storing the complex hierarchical explanations (e.g., `Trend: +0.4, MACD: +0.2`) in an adjacent `ExplanationStore` keyed by `forecast_id`, we preserve C-level vectorization speeds while maintaining perfect explainability for audits.

## Decision 3: The `FeatureManifest` & Lazy DAG Execution

To guarantee 100% Traceability (Research Replay), we introduced the `FeatureManifest`. Additionally, we updated the `FeatureStore` to perform **Lazy Execution**.

* **Rationale**: If a `Trend` model only requires `MACD`, the `FeatureStore` will automatically trim the DAG and only compute the `MACD` sub-graph, ignoring the 100 other registered features. The exact sub-graph and cache hashes are then permanently recorded in the `FeatureManifest`. When combined with the `alpha_id`, this forms the `forecast_id`, proving exactly *how* a specific signal was generated on a specific timestamp.

## Decision 4: Continuous Score and Rich Metadata

Forecasts emit a continuous score (-1.0 to 1.0) rather than discrete triggers. Furthermore, they are augmented with `confidence` (statistical certainty), `quality` (data integrity), `horizon` (holding period), and `half_life` (signal decay).

* **Rationale**: This allows the downstream `AlphaEnsemble` and `Optimizer` to mathematically blend signals. For example, a high-score signal with low confidence and rapid half-life can be dynamically down-weighted in a high-volatility regime.

## Status

Approved and implemented in M14B.
