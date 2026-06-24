# ADR-0021: Value-at-Risk (VaR) Engine Architecture

## Context

In M11A, GQOS required a mechanism to quantify the absolute risk of loss within a given confidence interval. Specifically, we needed to calculate Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR). Consistent with our Quantitative Philosophy, the engine needed to be stateless, immutable, and strictly decoupled from the core Accounting pipeline.

## Decision 1: Domain Segregation (`gqos.risk.var`)

We placed the VaR engines in a dedicated module (`gqos.risk.var`) rather than bloating the `accounting` or `portfolio` modules.

* **Rationale**: VaR is a predictive risk measure, not a historical fact. Placing it in the risk domain clarifies that it utilizes accounting state (Open Positions) as an input, but fundamentally serves a different domain concern (Risk Quantification).

## Decision 2: Current Positions vs. Historical NAV

The VaR engines evaluate risk by applying historical return shocks to the *Current Open Positions*, rather than analyzing the Strategy's historical NAV returns.

* **Rationale**: A Strategy's NAV curve reflects past trading decisions that may no longer exist in the portfolio. Shocking the *current* holdings answers the true risk question: "If the market collapses today, how much will my current portfolio lose?"

## Decision 3: Engine Polarity (Historical vs. Parametric)

We established `IVaREngine` as an interface and implemented two concrete engines:
1. `HistoricalVaREngine`: Our primary engine. Uses empirical shock distributions (non-parametric).
2. `ParametricVaREngine`: A secondary adapter that assumes normally distributed returns (Variance-Covariance).

* **Rationale**: `HistoricalVaREngine` is objectively superior for robust Quant systems because it makes no assumptions about the normality of returns, fully capturing fat tails and asymmetric payoffs inherent in modern markets. The `ParametricVaREngine` is provided primarily for academic benchmarking and speed-optimized comparisons.

## Decision 4: Pure Functional State

The VaR engines are implemented as Pure Functions (`calculate_var`, `calculate_cvar`). They hold zero internal state.

* **Rationale**: Ensures perfect deterministic replayability. By passing in the exact `positions` and `historical_returns`, the engine will always produce the exact same `VaRResult`. This satisfies the GQOS strict requirement for zero layer leakage.

## Status

Approved and implemented in M11A.
