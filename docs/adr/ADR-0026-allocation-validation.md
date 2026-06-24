# ADR-0026: Allocation Validation & Sensitivity Reporting

## Context

In M12C, GQOS introduced analytical frameworks to validate the robustness and determinism of Portfolio Optimization outputs. A central debate was whether a `SensitivityAnalyzer` should actively *reject* a portfolio if it deemed the optimizer's output to be overly sensitive to noise (the "Error Maximization" problem).

## Decision 1: Reporting vs. Enforcement

The `SensitivityAnalyzer` is strictly a Reporting/Telemetry tool. It computes the `SensitivityResult` (quantifying total turnover and individual weight drift caused by input permutations) but it **does not** reject the `OptimizationProblem` or raise exceptions upon detecting high sensitivity.

* **Rationale**: Instability is a mathematical characteristic of the Mean-Variance model, not a fatal software error. Rejecting portfolios based on arbitrary sensitivity thresholds is a Portfolio Governance/Policy decision. By emitting a `SensitivityResult`, we provide the Risk Manager with the data required to intervene, without hardcoding restrictive assumptions into the execution pipeline.

## Decision 2: In-Memory Optimizer Regression

The `OptimizerRegressionHarness` uses pure-Python, deterministic, in-memory constraints and matrices to evaluate regression baselines, rather than loading JSON fixtures from disk.

* **Rationale**: Deterministic mathematical regression should not rely on external disk states (which can become stale, corrupted, or drift between branches). By hardcoding the regression baseline `expected_hash` directly into the test suite, we guarantee that if the internal logic of `scipy.optimize` changes during a package update, the `RegressionDriftDetectedError` will instantly alert developers that the exact same inputs are no longer producing the exact same weights.

## Status

Approved and implemented in M12C.
