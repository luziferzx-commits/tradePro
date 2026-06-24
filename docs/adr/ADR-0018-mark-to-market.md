# ADR-0018: Mark-to-Market Engine and Valuation Pull Model

## Context

In M10B, GQOS required a mechanism to compute Unrealized PnL (Mark-to-Market value) for open positions. The primary consumer of this data is the `PortfolioSnapshotStage`, which feeds the exact, dynamically adjusted Total Equity (Net Asset Value) into the Sizing Engines (e.g. for dynamic Kelly allocations). A secondary requirement is generating periodic Equity Curve snapshots for drawdown evaluation.

## Decision 1: Isolation of Valuation from Accounting

We created a distinct `ValuationEngine` rather than building MTM logic directly into the `AccountingEngine`.

* **Rationale**: The `AccountingEngine` is responsible for strictly deterministic, realized facts (settled trades, explicit fee deductions). Valuation represents floating, ephemeral estimates that change on every market tick. Mixing them violates the Single Responsibility Principle.

## Decision 2: The "Pull" (On-Demand) Model

We implemented an **On-Demand (Pull)** model for fetching Unrealized PnL. The Sizing pipeline explicitly requests the NAV from the `ValuationEngine` whenever it evaluates a new trade. The system **does not** emit `PortfolioValuationUpdatedEvent` on every market data tick.

* **Rationale**: In a system tracking hundreds of assets with high-frequency data feeds, emitting an event to the global Event Bus on every price change for every position would cause severe event bloat, lagging the core execution pipeline, and destroying the purity of the Event Store's deterministic ledger.

## Decision 3: Periodic Snapshotting

For tracking equity curves and drawdowns, the `ValuationEngine` exposes a `snapshot_equity_curve` method.

* **Rationale**: This enforces that capturing the equity curve is an explicit, scheduled action (e.g. End-of-Day, End-of-Hour) driven by a cron or scheduler, rather than being inadvertently tied to the noise of the real-time data feed.

## Decision 4: Injecting MTM into Sizing

`PortfolioManager.generate_snapshot` was expanded to accept the calculated `unrealized_pnl` from the pipeline. 

* **Rationale**: This keeps `PortfolioManager` entirely decoupled from market data dependencies, while ensuring that the Sizing Engine correctly perceives its True Equity (`Allocated Settled Capital + Unrealized PnL`) rather than statically settled capital. 

## Status

Approved and implemented in M10B.
