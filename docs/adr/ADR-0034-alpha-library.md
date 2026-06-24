# ADR-0034: Alpha Library and Feature Governance

## Context

In M16, GQOS transitioned from building structural framework modules into researching and implementing actual quantitative trading strategies ("The First Ferrari"). The implementation required establishing strict rules for how mathematical signals are calculated and interpreted to prevent issues commonly found in retail algorithmic trading (e.g., lookahead bias, data snooping, and package dependency conflicts).

## Decision 1: Pure pandas/numpy Features

We decided to ban external indicator libraries (such as `pandas_ta`, `ta-lib`, or `finta`) for core feature calculation. All M16 features (`MacdFeature`, `RsiFeature`, etc.) were implemented using raw `pandas` and `numpy`.

* **Rationale**: Strict institutional environments mandate total control over logic execution. Implementing formulas manually ensures mathematically deterministic outcomes, minimizes the dependency surface (reducing future package deprecation risks), and makes the exact methodology fully auditable.

## Decision 2: Feature Version Locks

Each `IFeature` enforces a `version` string in its `FeatureMetadata` (e.g., `MACD_v1`).

* **Rationale**: As research evolves, a Quant might alter the smoothing mechanism of MACD (e.g., from EMA to Wilder's Smoothing). If an Alpha Model blindly requests "MACD", it would suddenly consume different data, destroying replayability. Version locks guarantee that `MomentumPack_v1` explicitly queries the exact mathematical formula it was trained on.

## Decision 3: Symbol-Independent Alpha Computation

Alpha Models do not handle internal `groupby("symbol")` logic. They receive a single generic `pd.DataFrame` per execution context.

* **Rationale**: The responsibility of Universe Management belongs to the Research Orchestrator. By keeping Alpha Models ignorant of the multi-asset universe structure, we decouple signal generation from portfolio scale. The Alpha Model simply evaluates price series logic, allowing it to be effortlessly applied to AAPL, TSLA, or BTCUSD sequentially or in parallel by upstream infrastructure.

## Decision 4: Cross-Sectional & Rolling Z-Scores

Unbounded features (like MACD or ATR) are forced through a `RollingZScoreFeature` before reaching the Alpha Model.

* **Rationale**: Since `StaticWeightEnsemble` averages scores, all scores must be rigorously bounded between $[-1, 1]$. Injecting a raw MACD value of `45.2` into an ensemble would completely overpower bounded signals (like `0.7` from RSI). The Z-Score ensures homoscedastic normalization across all feature spaces.

## Decision 5: Alpha Benchmark Suite

We implemented an `AlphaBenchmarkSuite` to generate quantitative reports (`Hit Rate`, `Signal Density`, `Turnover`, `Forecast Distribution`) for every model.

* **Rationale**: Before an Alpha Model can be promoted to Production, its profile must be understood. An Alpha with 99% Turnover and 5% Signal Density behaves fundamentally differently than one with 2% Turnover and 80% Density. This telemetry allows the Chief Quant Architect to construct diversified Ensembles without overlapping biases.

## Status

Approved and implemented in M16.
