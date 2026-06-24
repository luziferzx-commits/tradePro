# ADR-0019: Performance Attribution and Return Modeling

## Context

In M10C, GQOS required a `PerformanceAttributionEngine` to transform raw accounting facts (M10A) and floating valuations (M10B) into granular return categorizations. The goal is to answer *why* the portfolio generated its returns and to calculate true performance metrics (Time-Weighted Return and Money-Weighted Return).

## Decision 1: Hybrid Processing Model (Event Subscriber vs. On-Demand)

We implemented a **Hybrid Model**:
1. **Event Subscriber**: The engine continuously listens to `RealizedPnLEmittedEvent`, `FeeChargedEvent`, and `TradeExecutedEvent` to incrementally bucket PnL by Strategy, Symbol, Sector, and calculate cumulative Fees and Slippage.
2. **On-Demand Query**: The engine calculates Time-Weighted Return (TWR) and Money-Weighted Return (MWR) strictly *on-demand* rather than continuously.

* **Rationale**: Simple buckets (Strategy PnL, Fee sum) are computationally trivial and perfect for event-driven aggregation. Conversely, TWR and MWR require evaluating arrays of historical snapshots and cash flows, which is computationally expensive and unnecessary to perform on every tick.

## Decision 2: Slippage Data Source Boundary

We explicitly modified `TradeExecutedEvent` to include `intended_price` and `slippage_amount`, injecting this responsibility at the Execution/Accounting boundary.

* **Rationale**: This prevents the `PerformanceAttributionEngine` from having to query the Event Store for historical `SizePositionCommand` events to reverse-engineer the intended price. The Attribution Engine remains a pure reader of explicitly recorded facts.

## Decision 3: TWR vs MWR Cash Flow Handling

We implemented two distinct return models:
- **Time-Weighted Return (TWR)**: Neutralizes the impact of external capital injections/withdrawals by compounding sub-period returns. Cash flows are added to the starting NAV of the sub-period they occur in.
- **Money-Weighted Return (MWR / Modified Dietz)**: Evaluates the timing of capital flows. Cash flows are weighted by the proportion of the period they were invested in the portfolio.

* **Rationale**: TWR is required to evaluate the pure performance of the Quant Strategy algorithms independent of the investor's deposit/withdrawal timing. MWR is required to understand the true cash-on-cash IRR of the actual capital deployed.

## Decision 4: Interface-based Security Master

We introduced `ISecurityMaster` (and a `MockSecurityMaster`) to resolve `Symbol -> Sector` mappings instead of hardcoding metadata.

* **Rationale**: Maintains the decoupled "Platform before Intelligence" philosophy. If a symbol is missing, it fails gracefully into an `UNCLASSIFIED` bucket, ensuring total PnL reconciliation is never broken.

## Status

Approved and implemented in M10C.
