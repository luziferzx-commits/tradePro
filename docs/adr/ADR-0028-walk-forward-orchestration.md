# ADR-0028: Walk-Forward Orchestration & Leakage Guards

## Context

In M13B, GQOS implemented `WalkForwardOrchestration` to facilitate backtesting. The central challenge in any quantitative research platform is preventing "Data Snooping" and "Look-Ahead Bias", which frequently occurs if train and test datasets inadvertently overlap, or if researchers cheat by utilizing future data points.

## Decision 1: Pure Timeline Generation

The `WalkForwardGenerator` acts purely as a stateless timeline math engine. It does not load data, and it does not execute strategy backtests. It exclusively accepts a `dataset_hash` and time durations (e.g., `relativedelta(months=6)`) and yields a `FoldManifest`.

* **Rationale**: By isolating the generation of `WalkForwardFold`s from the `IStrategyEvaluator`, we can independently test the strict mathematical boundaries of our walk-forward logic (Rolling vs. Expanding) without the massive overhead of spinning up the execution loops.

## Decision 2: Hard Leakage Validation

Every `WalkForwardFold` executes an immutable `validate_leakage()` check upon instantiation. It strictly verifies:
1. `train_end <= test_start` (No overlap)
2. `train_end <= gap_start <= gap_end <= test_start` (Gap embargo is respected)

* **Rationale**: Many systems allow users to accidentally define an overlapping $Train$ and $Test$ window, which leaks future information into the model and generates artificially high out-of-sample Sharpe ratios. Hard validation prevents a fold from even existing if it violates the timeline sequence.

## Decision 3: Deterministic Fold Identity

Every fold exposes a `fold_id` calculated via SHA-256 hash of the `dataset_hash` and the ISO-8601 timestamps of its internal windows.

* **Rationale**: If a dataset updates (e.g., historical ticks are corrected), the `dataset_hash` changes, which cascades and mutates every `fold_id`. This prevents a researcher from mistakenly comparing an old experiment against a new experiment if the underlying data shifted.

## Status

Approved and implemented in M13B.
