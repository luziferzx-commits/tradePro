# ADR-0020: Risk-Adjusted Performance Metrics Architecture

## Context

In M10D, GQOS required the capability to evaluate the quality and risk profile of strategy returns. While M10C (`PerformanceAttributionEngine`) successfully tracks the nominal sources of returns (Strategy, Symbol, Sector, TWR, MWR), it does not quantify the *volatility* or *tail risk* experienced to achieve those returns. We needed to implement standard institutional metrics: Sharpe Ratio, Sortino Ratio, Calmar Ratio, Max Drawdown, and Rolling Profit Factor.

## Decision 1: Architectural Separation (RiskMetricsEngine vs AttributionEngine)

We created a distinct `RiskMetricsEngine` separate from the `PerformanceAttributionEngine`.

* **Rationale**: The `PerformanceAttributionEngine` focuses purely on "Where did the money come from?" and "What is the true nominal return?". The `RiskMetricsEngine` focuses on "Was this return worth the risk taken?". By separating these concerns, we prevent the Attribution Engine from becoming a monolithic "Kitchen Sink" class. 

## Decision 2: On-Demand Evaluation Model

Risk-adjusted metrics are exclusively computed on-demand by passing arrays of `NavSnapshot` objects and PnL events to the engine.

* **Rationale**: Computing standard deviation and iterating over equity curves for drawdowns are O(N) operations. Performing these calculations on every market tick or event bus broadcast would severely degrade pipeline throughput. These metrics are inherently intended for periodic end-of-day or end-of-month reporting.

## Decision 3: Zero-Edge Handling

We explicitly coded safeguards for absolute edge cases:
- Zero volatility (perfectly straight NAV curves) returns a `0` Sharpe/Sortino to prevent `ZeroDivisionError`.
- Zero drawdown returns a `0` Calmar Ratio.
- Zero-loss scenarios in the Rolling Profit Factor return a configurable theoretical maximum (`99999.0`).

* **Rationale**: Quant trading systems frequently encounter these states during initialization, testing, or periods of inactivity. Mathematical failures during evaluation cascades into reporting failures.

## Decision 4: Configurable Annualization Factor

The engine accepts a configurable `annualization_factor` upon initialization, defaulting to 252.

* **Rationale**: Traditional equity systems calculate annualized volatility using 252 trading days. However, cryptocurrency markets require 365 days. A hardcoded constant would render the platform inflexible for multi-asset class firms.

## Status

Approved and implemented in M10D.
