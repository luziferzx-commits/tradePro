# ADR-0023: Factor Analytics & Drawdown Attribution Architecture

## Context

In M11C, GQOS needed the capability to decompose the drivers of risk and return into underlying mathematical factors (e.g., Market Beta, Momentum, Size) rather than just Strategy nominal PnL. Additionally, when the portfolio experiences a Drawdown, the platform needed a deterministic mechanism to attribute exactly *where* the bleeding occurred.

## Decision 1: Domain Purity (`gqos.risk.analytics`)

We isolated the advanced Factor Model engines and the Drawdown Attribution engine into `gqos.risk.analytics`.

* **Rationale**: While `gqos.accounting.risk_metrics` evaluates *whether* a drawdown occurred and the *magnitude* of the Volatility/Sharpe, the deep-dive *causes* of those metrics belong in a dedicated analytics domain. This keeps standard reporting lightweight and defers heavy decompositions to explicit analytical engines.

## Decision 2: Factor Model Abstraction

The `FactorExposureEngine` depends exclusively on the `IFactorModel` interface, isolating it from data vendors. A deterministic `MockFactorModel` was implemented for testing.

* **Rationale**: Institutional platforms typically switch between proprietary PCA factor discovery, Axioma, or Barra data feeds. Hardcoding assumptions about Factor structures prevents future Vendor integration.

## Decision 3: Drawdown Attribution via Total Equity Delta

The `DrawdownAttributionEngine` computes attribution by calculating the delta between a Symbol's Total Equity (Realized + Unrealized) at the Peak timestamp vs the Trough timestamp.

* **Rationale**: Relying purely on Realized PnL during a drawdown window is highly inaccurate, as massive MTM losses may remain open (unrealized) at the bottom of the trough. By passing the isolated Peak vs Trough equity states, the Engine operates deterministically and accurately captures the true loss contribution.

## Decision 4: Idiosyncratic Residual Isolation

When computing `FactorReturnAttributionResult`, any return that cannot be explained by the Factor Exposures is strictly bucketed as `specific_return`.

* **Rationale**: This guarantees mathematical reconciliation (`Total Return = Sum(Factor Returns) + Specific Return`). The `specific_return` effectively represents the Strategy's pure Alpha / idiosyncratic stock-picking edge.

## Status

Approved and implemented in M11C.
